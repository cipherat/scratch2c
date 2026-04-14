# Adding Opcodes

Supporting a new Scratch block requires changes in 1-4 files depending on whether it's a statement or expression, and whether it needs a new IR node.

## Step 1: Find the opcode

Open the `.sb3` as a ZIP, read `project.json`, and find the block's `opcode` field. Example:

```bash
unzip -o project.sb3 project.json
python3 -c "
import json
blocks = json.load(open('project.json'))['targets'][1]['blocks']
for bid, b in blocks.items():
    if isinstance(b, dict):
        print(b['opcode'])
" | sort -u
```

The [Scratch wiki](https://en.scratch-wiki.info/wiki/Scratch_File_Format) documents all opcodes.

## Step 2: Statement or expression?

- **Statement**: does something (set variable, say, repeat). Has a `next` pointer.
- **Expression** (reporter): returns a value (add, join, contains). Referenced from another block's inputs.

## Adding a statement (reusing an existing IR node)

If the new opcode maps to an existing IR concept (e.g., `sensing_askandwait` can reuse `Say`), you only touch `ir_builder.py`:

```python
# 1. Add to _get_statement_builders()
def _get_statement_builders() -> dict:
    return {
        # ... existing ...
        "sensing_askandwait": _stmt_ask_and_wait,
    }

# 2. Write the builder
def _stmt_ask_and_wait(block: dict, blocks: dict) -> Say:
    question = _resolve_input(block, "QUESTION", blocks)
    return Say(message=question)
```

Done. Type inference and codegen already know how to handle `Say`.

## Adding a statement (new IR node)

If you need a new concept:

```python
# 1. ir.py — add the dataclass
@dataclass
class PlaySound:
    sound_name: Expression

# 2. ir.py — add to the Statement union
Statement = Union[
    SetVariable, ChangeVariable, Say, ..., PlaySound,
]

# 3. ir_builder.py — add builder (same as above)

# 4. codegen/base.py → _emit_statement() — add handling
elif isinstance(stmt, PlaySound):
    name_code = self._emit_expr_as_string(stmt.sound_name, variables)
    self._emit(f"/* play sound: {name_code} — not supported in C */")

# 5. type_inference.py → _scan_statements() and _propagate_statements()
# Add traversal if the node contains sub-expressions or nested bodies
```

## Adding an expression

Edit `_build_expression()` in `ir_builder.py`. Most expressions map to `CallExpr` with a runtime function:

```python
# ir_builder.py → _build_expression()
if opcode == "operator_round":
    operand = _resolve_input(block, "NUM", blocks)
    return CallExpr(func="scratch_round", args=[operand])
```

Then register the function's type information in three places:

```python
# type_inference.py → _classify_expression()
if expr.func == "scratch_round":
    return ScratchType.LONG

# type_inference.py → _propagate_expr_context()
elif expr.func == "scratch_round":
    _propagate_expr_context(expr.args[0], ScratchType.LONG, variables)

# codegen/base.py → _expr_type()
if expr.func in ("scratch_strlen", "scratch_contains", "scratch_round"):
    return ScratchType.LONG
```

If the function returns a string (like `scratch_join`), add it to the string-returning sets instead.

For functions that need special argument handling in codegen (e.g., mixed string and numeric args), add a case in `_emit_call()`:

```python
# codegen/base.py → _emit_call()
if expr.func == "scratch_letter_of":
    idx = self._emit_expr_as_long(expr.args[0], variables)
    s = self._emit_expr_as_string(expr.args[1], variables)
    return f"scratch_letter_of({idx}, {s})"
```

Finally, add the C implementation to `runtime/scratch_runtime.h`:

```c
static inline long scratch_round(long n) {
    return n;  /* Already integer in our type system */
}
```

## Step 3: Write a test

```python
# tests/test_ir_builder.py
def test_my_new_opcode(self):
    project_json = {
        "targets": [{
            "isStage": True, "name": "Stage", "variables": {},
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "myblock", "parent": None,
                    "inputs": {}, "fields": {},
                    "shadow": False, "topLevel": True,
                },
                "myblock": {
                    "opcode": "sensing_askandwait",
                    "next": None, "parent": "hat",
                    "inputs": {"QUESTION": [1, [10, "What's your name?"]]},
                    "fields": {},
                    "shadow": False, "topLevel": False,
                },
            },
        }],
    }
    project = build_ir(project_json)
    body = project.sprites[0].scripts[0].body
    assert len(body) == 1
    assert isinstance(body[0], Say)
```

## Checklist

| File | When needed |
|------|-------------|
| `ir_builder.py` | Always |
| `ir.py` | Only if new IR node |
| `type_inference.py` | If new IR node or new CallExpr function |
| `codegen/base.py` | If new IR node or new CallExpr needing special emit |
| `runtime/scratch_runtime.h` | If new CallExpr with a runtime function |
| `tests/` | Always |
