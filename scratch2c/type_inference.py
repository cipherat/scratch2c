"""
Type inference for scratch2c.

Scratch variables are dynamically typed — any variable can hold a number or
a string at any time. C doesn't work that way, so we need to pick a type for
each variable before code generation.

Strategy (two passes):

  Pass 1 — Collect assignments:
    Walk every statement. If a variable is assigned the result of an arithmetic
    operation or changevariableby, mark it LONG. If it's assigned a join() or
    a string literal that doesn't parse as a number, mark it STRING.

  Pass 2 — Propagate through expressions:
    Not strictly necessary for variable typing, but we use this pass to verify
    consistency and resolve UNKNOWN variables. If a variable is used in
    arithmetic context and never assigned a string, it becomes LONG.
    If nothing pins it, default to LONG (Scratch's default behavior for
    uninitialized variables).

NOTE: This is deliberately simple. A full Scratch VM would need tagged unions
at runtime. We accept that some exotic programs will be mis-typed. The goal
is correctness for the common case, not completeness.
"""

from __future__ import annotations

from .ir import (
    BinaryOp, CallExpr, ChangeVariable, Expression, Forever, IfThen,
    IfThenElse, Literal, Procedure, Project, Repeat, RepeatUntil,
    Say, ScratchType, SetVariable, Statement, UnaryOp, Variable,
    VariableRef, Wait, WaitUntil, ProcedureCall,
)


def infer_types(project: Project) -> None:
    """Run type inference over the project IR, mutating Variable.inferred_type in place.

    Args:
        project: A fully-built Project IR. Variables will have their
                 inferred_type updated from UNKNOWN to LONG or STRING.
    """
    all_vars = project.all_variables()

    # Pass 1: scan assignments
    for sprite in project.sprites:
        for script in sprite.scripts:
            _scan_statements(script.body, all_vars)
        for proc in sprite.procedures.values():
            _scan_statements(proc.body, all_vars)

    # Pass 2: scan expression contexts to resolve remaining UNKNOWNs
    for sprite in project.sprites:
        for script in sprite.scripts:
            _propagate_statements(script.body, all_vars)
        for proc in sprite.procedures.values():
            _propagate_statements(proc.body, all_vars)

    # Final: default any remaining UNKNOWN to LONG
    for var in all_vars.values():
        if var.inferred_type == ScratchType.UNKNOWN:
            var.inferred_type = ScratchType.LONG


# ---------------------------------------------------------------------------
# Pass 1: Assignment scanning
# ---------------------------------------------------------------------------

def _scan_statements(stmts: list[Statement], variables: dict[str, Variable]) -> None:
    """Walk statements and classify variables based on their assignments."""
    for stmt in stmts:
        if isinstance(stmt, SetVariable):
            vtype = _classify_expression(stmt.value)
            _update_var_type(stmt.var_id, vtype, variables)

        elif isinstance(stmt, ChangeVariable):
            # changevariableby always implies numeric
            _update_var_type(stmt.var_id, ScratchType.LONG, variables)

        elif isinstance(stmt, (Repeat, Forever, RepeatUntil)):
            _scan_statements(stmt.body, variables)

        elif isinstance(stmt, IfThen):
            _scan_statements(stmt.then_body, variables)

        elif isinstance(stmt, IfThenElse):
            _scan_statements(stmt.then_body, variables)
            _scan_statements(stmt.else_body, variables)


def _classify_expression(expr: Expression) -> ScratchType:
    """Determine the type an expression produces."""
    if isinstance(expr, Literal):
        return _classify_literal(expr.value)

    if isinstance(expr, BinaryOp):
        if expr.operator in ("+", "-", "*", "/", "%"):
            return ScratchType.LONG
        # Comparisons and booleans produce integers (0/1) in C
        return ScratchType.LONG

    if isinstance(expr, UnaryOp):
        return ScratchType.LONG  # !x is always numeric

    if isinstance(expr, CallExpr):
        if expr.func in ("scratch_join", "scratch_letter_of"):
            return ScratchType.STRING
        if expr.func == "scratch_strlen":
            return ScratchType.LONG
        return ScratchType.UNKNOWN

    if isinstance(expr, VariableRef):
        return ScratchType.UNKNOWN  # can't tell from a read alone

    return ScratchType.UNKNOWN


def _classify_literal(value: str) -> ScratchType:
    """Is this literal a number or a string?"""
    try:
        # Accept integers and floats
        float(value)
        return ScratchType.LONG
    except (ValueError, TypeError):
        return ScratchType.STRING


def _update_var_type(
    var_id: str, new_type: ScratchType, variables: dict[str, Variable]
) -> None:
    """Update a variable's type, handling conflicts.

    If a variable is assigned both numeric and string values, STRING wins
    because we'd rather allocate a buffer than truncate a string into a long.
    """
    if var_id not in variables:
        return
    var = variables[var_id]
    if var.inferred_type == ScratchType.UNKNOWN:
        var.inferred_type = new_type
    elif var.inferred_type != new_type and new_type != ScratchType.UNKNOWN:
        # Conflict: string wins (safe fallback)
        var.inferred_type = ScratchType.STRING


# ---------------------------------------------------------------------------
# Pass 2: Context propagation
# ---------------------------------------------------------------------------

def _propagate_statements(stmts: list[Statement], variables: dict[str, Variable]) -> None:
    """Walk statements and use expression context to resolve remaining UNKNOWNs."""
    for stmt in stmts:
        if isinstance(stmt, SetVariable):
            _propagate_expr_context(stmt.value, ScratchType.UNKNOWN, variables)

        elif isinstance(stmt, ChangeVariable):
            # The delta is always used as a number
            _propagate_expr_context(stmt.delta, ScratchType.LONG, variables)

        elif isinstance(stmt, Say):
            # say can accept any type
            _propagate_expr_context(stmt.message, ScratchType.UNKNOWN, variables)

        elif isinstance(stmt, Repeat):
            _propagate_expr_context(stmt.count, ScratchType.LONG, variables)
            _propagate_statements(stmt.body, variables)

        elif isinstance(stmt, Forever):
            _propagate_statements(stmt.body, variables)

        elif isinstance(stmt, RepeatUntil):
            _propagate_expr_context(stmt.condition, ScratchType.LONG, variables)
            _propagate_statements(stmt.body, variables)

        elif isinstance(stmt, WaitUntil):
            _propagate_expr_context(stmt.condition, ScratchType.LONG, variables)

        elif isinstance(stmt, IfThen):
            _propagate_expr_context(stmt.condition, ScratchType.LONG, variables)
            _propagate_statements(stmt.then_body, variables)

        elif isinstance(stmt, IfThenElse):
            _propagate_expr_context(stmt.condition, ScratchType.LONG, variables)
            _propagate_statements(stmt.then_body, variables)
            _propagate_statements(stmt.else_body, variables)

        elif isinstance(stmt, ProcedureCall):
            for arg in stmt.args:
                _propagate_expr_context(arg, ScratchType.UNKNOWN, variables)


def _propagate_expr_context(
    expr: Expression, context: ScratchType, variables: dict[str, Variable]
) -> None:
    """If a variable is used in a typed context and is still UNKNOWN, pin it."""
    if isinstance(expr, VariableRef):
        if context != ScratchType.UNKNOWN and expr.var_id in variables:
            var = variables[expr.var_id]
            if var.inferred_type == ScratchType.UNKNOWN:
                var.inferred_type = context

    elif isinstance(expr, BinaryOp):
        if expr.operator in ("+", "-", "*", "/", "%"):
            # Both operands should be numeric
            _propagate_expr_context(expr.left, ScratchType.LONG, variables)
            _propagate_expr_context(expr.right, ScratchType.LONG, variables)
        else:
            _propagate_expr_context(expr.left, context, variables)
            _propagate_expr_context(expr.right, context, variables)

    elif isinstance(expr, UnaryOp):
        _propagate_expr_context(expr.operand, ScratchType.LONG, variables)

    elif isinstance(expr, CallExpr):
        if expr.func == "scratch_join":
            for arg in expr.args:
                _propagate_expr_context(arg, ScratchType.STRING, variables)
        elif expr.func == "scratch_strlen":
            for arg in expr.args:
                _propagate_expr_context(arg, ScratchType.STRING, variables)
        elif expr.func == "scratch_letter_of":
            if len(expr.args) >= 1:
                _propagate_expr_context(expr.args[0], ScratchType.LONG, variables)
            if len(expr.args) >= 2:
                _propagate_expr_context(expr.args[1], ScratchType.STRING, variables)
