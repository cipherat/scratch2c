"""
IR builder: converts Scratch 3 project.json into the scratch2c IR.

Scratch 3 represents programs as a flat dict of blocks keyed by random IDs.
Each block has an "opcode", "inputs" (child expressions), "fields" (literals),
and a "next" pointer to the following statement. This module walks that graph
and produces the structured IR defined in ir.py.

The core pattern:
  - Top-level blocks (blocks with no parent) are either hat blocks or
    procedure definitions.
  - Hat blocks start scripts; we follow the "next" chain to build the body.
  - Inputs can reference other blocks (sub-expressions) or contain literal
    values packed in Scratch's array-based encoding.

NOTE: Scratch's input encoding is baroque. A value like [1, [10, "42"]] means
"a literal number 42". See _resolve_input() for the gory details.
"""

from __future__ import annotations

import re
from typing import Any

from .ir import (
    BinaryOp, CallExpr, ChangeVariable, Expression, Forever, HatBlock,
    HatKind, IfThen, IfThenElse, Literal, Procedure, ProcedureCall,
    Project, Repeat, RepeatUntil, Say, Script, SetVariable, Sprite,
    Statement, Stop, UnaryOp, Variable, VariableRef, Wait, WaitUntil,
)


def build_ir(project_json: dict) -> Project:
    """Convert a parsed project.json dict into a Project IR.

    Args:
        project_json: The raw parsed JSON from a .sb3 file.

    Returns:
        A fully-built Project IR (types still UNKNOWN — run type inference next).
    """
    project = Project()
    for target in project_json.get("targets", []):
        sprite = _build_sprite(target)
        project.sprites.append(sprite)
    return project


def _build_sprite(target: dict) -> Sprite:
    """Build a Sprite IR from a Scratch target dict."""
    name = target.get("name", "Sprite")
    sprite = Sprite(name=name)

    # --- Variables ---
    for var_id, var_info in target.get("variables", {}).items():
        # var_info is [name, initial_value]
        var_name = var_info[0] if isinstance(var_info, list) else str(var_info)
        initial = str(var_info[1]) if isinstance(var_info, list) and len(var_info) > 1 else "0"
        sprite.variables[var_id] = Variable(var_id=var_id, name=var_name, initial_value=initial)

    blocks = target.get("blocks", {})
    if not isinstance(blocks, dict):
        return sprite

    # --- Find top-level blocks (no parent) ---
    for block_id, block in blocks.items():
        if not isinstance(block, dict):
            continue
        if block.get("topLevel", False):
            opcode = block.get("opcode", "")
            if opcode == "procedures_definition":
                proc = _build_procedure(block_id, blocks)
                if proc:
                    sprite.procedures[proc.name] = proc
            elif opcode.startswith("event_"):
                script = _build_script(block_id, blocks)
                if script:
                    sprite.scripts.append(script)

    return sprite


# ---------------------------------------------------------------------------
# Procedure definitions
# ---------------------------------------------------------------------------

def _build_procedure(def_block_id: str, blocks: dict) -> Procedure | None:
    """Build a Procedure from a procedures_definition block."""
    def_block = blocks[def_block_id]
    # procedures_definition has input "custom_block" pointing to the prototype
    proto_id = _get_input_block_id(def_block, "custom_block")
    if not proto_id or proto_id not in blocks:
        return None
    proto = blocks[proto_id]

    proccode = proto.get("mutation", {}).get("proccode", "unnamed")
    # Clean the proccode to get a C-safe function name
    proc_name = _sanitize_name(proccode)

    # Extract argument names and IDs from the prototype
    arg_ids_json = proto.get("mutation", {}).get("argumentids", "[]")
    arg_names_json = proto.get("mutation", {}).get("argumentnames", "[]")
    import json
    try:
        arg_ids = json.loads(arg_ids_json)
        arg_names = json.loads(arg_names_json)
    except (json.JSONDecodeError, TypeError):
        arg_ids = []
        arg_names = []

    body = _build_body(def_block.get("next"), blocks)
    return Procedure(
        name=proc_name,
        param_names=[_sanitize_name(n) for n in arg_names],
        param_ids=arg_ids,
        body=body,
    )


# ---------------------------------------------------------------------------
# Scripts (hat block + body)
# ---------------------------------------------------------------------------

def _build_script(block_id: str, blocks: dict) -> Script | None:
    """Build a Script from a hat block."""
    block = blocks[block_id]
    opcode = block.get("opcode", "")

    hat: HatBlock | None = None
    if opcode == "event_whenflagclicked":
        hat = HatBlock(kind=HatKind.FLAG_CLICKED)
    elif opcode == "event_whenbroadcastreceived":
        broadcast_name = _get_field_value(block, "BROADCAST_OPTION")
        if broadcast_name and broadcast_name.lower() == "exit":
            hat = HatBlock(kind=HatKind.BROADCAST_EXIT, broadcast_name=broadcast_name)
        elif broadcast_name and broadcast_name.lower() == "init":
            hat = HatBlock(kind=HatKind.BROADCAST_INIT, broadcast_name=broadcast_name)
        else:
            hat = HatBlock(kind=HatKind.BROADCAST_OTHER, broadcast_name=broadcast_name)
    else:
        # Unknown hat — skip
        return None

    body = _build_body(block.get("next"), blocks)
    return Script(hat=hat, body=body)


# ---------------------------------------------------------------------------
# Statement chain builder
# ---------------------------------------------------------------------------

def _build_body(block_id: str | None, blocks: dict) -> list[Statement]:
    """Follow a chain of 'next' pointers and build a statement list."""
    stmts: list[Statement] = []
    current_id = block_id
    while current_id and current_id in blocks:
        block = blocks[current_id]
        if not isinstance(block, dict):
            break
        stmt = _build_statement(current_id, block, blocks)
        if stmt is not None:
            stmts.append(stmt)
        current_id = block.get("next")
    return stmts


def _build_statement(block_id: str, block: dict, blocks: dict) -> Statement | None:
    """Dispatch a single block to the appropriate statement builder."""
    opcode = block.get("opcode", "")
    builders = _get_statement_builders()
    builder = builders.get(opcode)
    if builder:
        return builder(block, blocks)
    # NOTE: Unknown opcodes are silently skipped. This is deliberate —
    # we'd rather produce partial output than crash on unsupported blocks.
    return None


def _get_statement_builders() -> dict:
    """Registry of opcode → builder function for statements.

    NOTE: To add a new opcode, add one entry here and write the builder
    function. That's it — see CONTRIBUTING.md.
    """
    return {
        "data_setvariableto": _stmt_set_variable,
        "data_changevariableby": _stmt_change_variable,
        "looks_say": _stmt_say,
        "looks_sayforsecs": _stmt_say_for_secs,
        "control_repeat": _stmt_repeat,
        "control_forever": _stmt_forever,
        "control_repeat_until": _stmt_repeat_until,
        "control_wait_until": _stmt_wait_until,
        "control_if": _stmt_if,
        "control_if_else": _stmt_if_else,
        "control_stop": _stmt_stop,
        "control_wait": _stmt_wait,
        "procedures_call": _stmt_proc_call,
    }


# ---------------------------------------------------------------------------
# Statement builders
# ---------------------------------------------------------------------------

def _stmt_set_variable(block: dict, blocks: dict) -> SetVariable:
    var_id, var_name = _get_variable_field(block)
    value = _resolve_input(block, "VALUE", blocks)
    return SetVariable(var_id=var_id, var_name=var_name, value=value)

def _stmt_change_variable(block: dict, blocks: dict) -> ChangeVariable:
    var_id, var_name = _get_variable_field(block)
    delta = _resolve_input(block, "VALUE", blocks)
    return ChangeVariable(var_id=var_id, var_name=var_name, delta=delta)

def _stmt_say(block: dict, blocks: dict) -> Say:
    message = _resolve_input(block, "MESSAGE", blocks)
    return Say(message=message)

def _stmt_say_for_secs(block: dict, blocks: dict) -> Say:
    message = _resolve_input(block, "MESSAGE", blocks)
    duration = _resolve_input(block, "SECS", blocks)
    return Say(message=message, duration=duration)

def _stmt_repeat(block: dict, blocks: dict) -> Repeat:
    count = _resolve_input(block, "TIMES", blocks)
    body = _build_substack(block, "SUBSTACK", blocks)
    return Repeat(count=count, body=body)

def _stmt_forever(block: dict, blocks: dict) -> Forever:
    body = _build_substack(block, "SUBSTACK", blocks)
    return Forever(body=body)

def _stmt_repeat_until(block: dict, blocks: dict) -> RepeatUntil:
    condition = _resolve_input(block, "CONDITION", blocks)
    body = _build_substack(block, "SUBSTACK", blocks)
    return RepeatUntil(condition=condition, body=body)

def _stmt_wait_until(block: dict, blocks: dict) -> WaitUntil:
    condition = _resolve_input(block, "CONDITION", blocks)
    return WaitUntil(condition=condition)

def _stmt_if(block: dict, blocks: dict) -> IfThen:
    condition = _resolve_input(block, "CONDITION", blocks)
    then_body = _build_substack(block, "SUBSTACK", blocks)
    return IfThen(condition=condition, then_body=then_body)

def _stmt_if_else(block: dict, blocks: dict) -> IfThenElse:
    condition = _resolve_input(block, "CONDITION", blocks)
    then_body = _build_substack(block, "SUBSTACK", blocks)
    else_body = _build_substack(block, "SUBSTACK2", blocks)
    return IfThenElse(condition=condition, then_body=then_body, else_body=else_body)

def _stmt_stop(block: dict, blocks: dict) -> Stop:
    return Stop()

def _stmt_wait(block: dict, blocks: dict) -> Wait:
    duration = _resolve_input(block, "DURATION", blocks)
    return Wait(duration=duration)

def _stmt_proc_call(block: dict, blocks: dict) -> ProcedureCall:
    import json
    mutation = block.get("mutation", {})
    proccode = mutation.get("proccode", "unnamed")
    proc_name = _sanitize_name(proccode)

    arg_ids_json = mutation.get("argumentids", "[]")
    try:
        arg_ids = json.loads(arg_ids_json)
    except (json.JSONDecodeError, TypeError):
        arg_ids = []

    args: list[Expression] = []
    inputs = block.get("inputs", {})
    for aid in arg_ids:
        if aid in inputs:
            args.append(_resolve_input(block, aid, blocks))
        else:
            args.append(Literal(value="0"))

    return ProcedureCall(proc_name=proc_name, args=args)


# ---------------------------------------------------------------------------
# Expression builder
# ---------------------------------------------------------------------------

def _build_expression(block_id: str, blocks: dict) -> Expression:
    """Build an expression tree from a reporter block."""
    if block_id not in blocks:
        return Literal(value="0")
    block = blocks[block_id]
    if not isinstance(block, dict):
        return Literal(value=str(block))

    opcode = block.get("opcode", "")

    # Arithmetic operators
    arith_ops = {
        "operator_add": "+",
        "operator_subtract": "-",
        "operator_multiply": "*",
        "operator_divide": "/",
        "operator_mod": "%",
    }
    if opcode in arith_ops:
        left = _resolve_input(block, "NUM1", blocks)
        right = _resolve_input(block, "NUM2", blocks)
        return BinaryOp(operator=arith_ops[opcode], left=left, right=right)

    # Comparison operators
    cmp_ops = {
        "operator_lt": "<",
        "operator_gt": ">",
        "operator_equals": "==",
    }
    if opcode in cmp_ops:
        left = _resolve_input(block, "OPERAND1", blocks)
        right = _resolve_input(block, "OPERAND2", blocks)
        return BinaryOp(operator=cmp_ops[opcode], left=left, right=right)

    # Boolean operators
    if opcode == "operator_and":
        left = _resolve_input(block, "OPERAND1", blocks)
        right = _resolve_input(block, "OPERAND2", blocks)
        return BinaryOp(operator="&&", left=left, right=right)
    if opcode == "operator_or":
        left = _resolve_input(block, "OPERAND1", blocks)
        right = _resolve_input(block, "OPERAND2", blocks)
        return BinaryOp(operator="||", left=left, right=right)
    if opcode == "operator_not":
        operand = _resolve_input(block, "OPERAND", blocks)
        return UnaryOp(operator="!", operand=operand)

    # String operations
    if opcode == "operator_join":
        left = _resolve_input(block, "STRING1", blocks)
        right = _resolve_input(block, "STRING2", blocks)
        return CallExpr(func="scratch_join", args=[left, right])
    if opcode == "operator_length":
        string = _resolve_input(block, "STRING", blocks)
        return CallExpr(func="scratch_strlen", args=[string])
    if opcode == "operator_letter_of":
        index = _resolve_input(block, "LETTER", blocks)
        string = _resolve_input(block, "STRING", blocks)
        return CallExpr(func="scratch_letter_of", args=[index, string])

    # Variable reporter
    if opcode == "data_variable":
        var_id = _get_field_id(block, "VARIABLE")
        var_name = _get_field_value(block, "VARIABLE")
        return VariableRef(var_id=var_id or "", var_name=var_name or "unknown")

    # Procedure argument reporter
    if opcode == "argument_reporter_string_number" or opcode == "argument_reporter_boolean":
        arg_name = _get_field_value(block, "VALUE")
        return VariableRef(var_id=f"__arg_{arg_name}", var_name=arg_name or "arg")

    # Fallback: treat unknown reporters as literal 0
    return Literal(value="0")


# ---------------------------------------------------------------------------
# Input resolution helpers
# ---------------------------------------------------------------------------

def _resolve_input(block: dict, input_name: str, blocks: dict) -> Expression:
    """Resolve a block input to an Expression.

    Scratch inputs are encoded as arrays with a type tag:
      [1, [10, "42"]]           → literal number "42"
      [1, [4, "hello"]]         → literal string "hello"
      [3, "other_block_id", ...] → reference to another block
      [1, [12, "varname", "varid"]] → variable reporter shorthand

    This function handles the common cases. Uncommon encodings fall back
    to Literal("0") with a NOTE comment in the output.
    """
    inputs = block.get("inputs", {})
    if input_name not in inputs:
        return Literal(value="0")

    inp = inputs[input_name]
    if not isinstance(inp, list) or len(inp) < 2:
        return Literal(value="0")

    shadow_type = inp[0]
    value_part = inp[1]

    # Case 1: value_part is a block ID string → sub-expression
    if isinstance(value_part, str) and value_part in blocks:
        return _build_expression(value_part, blocks)

    # Case 2: value_part is an array (literal or variable shorthand)
    if isinstance(value_part, list) and len(value_part) >= 2:
        type_tag = value_part[0]
        # Type tags 4-10: literal values (number, string, etc.)
        if type_tag in (4, 5, 6, 7, 8, 9, 10):
            return Literal(value=str(value_part[1]))
        # Type tag 12: variable reporter shorthand [12, name, id]
        if type_tag == 12 and len(value_part) >= 3:
            return VariableRef(var_id=str(value_part[2]), var_name=str(value_part[1]))
        # Type tag 13: broadcast shorthand
        if type_tag == 13:
            return Literal(value=str(value_part[1]))
        return Literal(value=str(value_part[1]))

    # Case 3: null input (e.g., empty condition slot)
    if value_part is None:
        # Check if there's a shadow (third element)
        if len(inp) >= 3 and isinstance(inp[2], list):
            return Literal(value=str(inp[2][1]) if len(inp[2]) >= 2 else "0")
        return Literal(value="0")

    return Literal(value=str(value_part))


def _build_substack(block: dict, substack_name: str, blocks: dict) -> list[Statement]:
    """Resolve a SUBSTACK input to a statement body."""
    inputs = block.get("inputs", {})
    if substack_name not in inputs:
        return []
    inp = inputs[substack_name]
    if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], str):
        return _build_body(inp[1], blocks)
    return []


def _get_input_block_id(block: dict, input_name: str) -> str | None:
    """Get the block ID referenced by an input, if any."""
    inputs = block.get("inputs", {})
    if input_name not in inputs:
        return None
    inp = inputs[input_name]
    if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], str):
        return inp[1]
    return None


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _get_variable_field(block: dict) -> tuple[str, str]:
    """Extract (var_id, var_name) from a VARIABLE field."""
    fields = block.get("fields", {})
    var_field = fields.get("VARIABLE", [])
    if isinstance(var_field, list) and len(var_field) >= 2:
        return str(var_field[1]), str(var_field[0])
    return "", "unknown"

def _get_field_value(block: dict, field_name: str) -> str | None:
    """Get the human-readable value of a field (first element)."""
    fields = block.get("fields", {})
    f = fields.get(field_name)
    if isinstance(f, list) and len(f) >= 1:
        return str(f[0])
    return None

def _get_field_id(block: dict, field_name: str) -> str | None:
    """Get the ID of a field (second element, if present)."""
    fields = block.get("fields", {})
    f = fields.get(field_name)
    if isinstance(f, list) and len(f) >= 2:
        return str(f[1])
    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sanitize_name(name: str) -> str:
    """Convert a Scratch name to a valid C identifier.

    Replaces spaces and special chars with underscores, strips format
    specifiers like %s and %b from proccodes.
    """
    # Remove Scratch proccode argument placeholders
    cleaned = re.sub(r"%[snb]", "", name)
    # Replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", cleaned.strip())
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Strip leading/trailing underscores
    cleaned = cleaned.strip("_")
    # Ensure it doesn't start with a digit
    if cleaned and cleaned[0].isdigit():
        cleaned = "proc_" + cleaned
    return cleaned or "unnamed"
