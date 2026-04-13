# Contributing to scratch2c

## How to add a new Scratch opcode (< 10 minutes)

Adding support for a new block is the most common contribution. Here's exactly what to touch.

### Step 1: Decide if it's a statement or an expression

- **Statement** = a block that *does* something (set variable, say, repeat, if)
- **Expression** (reporter) = a block that *returns* a value (add, join, variable read)

### Step 2a: Adding a new statement

Edit **`scratch2c/ir_builder.py`** only:

1. Add your opcode to `_get_statement_builders()`:

```python
def _get_statement_builders() -> dict:
    return {
        # ... existing entries ...
        "sensing_askandwait": _stmt_ask_and_wait,  # ← add this
    }
```

2. Write the builder function right below the others:

```python
def _stmt_ask_and_wait(block: dict, blocks: dict) -> Say:
    # For now, treat "ask" like "say" — we can refine later
    message = _resolve_input(block, "QUESTION", blocks)
    return Say(message=message)
```

That's it. The IR, type inference, and code generation already know how to handle `Say` statements.

If your new opcode needs a **new IR node** (not just reusing an existing one):

3. Add a dataclass to `scratch2c/ir.py`:

```python
@dataclass
class AskAndWait:
    question: Expression
```

4. Add it to the `Statement` union type in `ir.py`
5. Handle it in `scratch2c/codegen/base.py` → `_emit_statement()`
6. Handle it in `scratch2c/type_inference.py` → both `_scan_statements()` and `_propagate_statements()`

### Step 2b: Adding a new expression (reporter)

Edit **`scratch2c/ir_builder.py`** → `_build_expression()`:

```python
def _build_expression(block_id: str, blocks: dict) -> Expression:
    # ... existing handlers ...

    # Add your new reporter here:
    if opcode == "operator_round":
        operand = _resolve_input(block, "NUM", blocks)
        return CallExpr(func="scratch_round", args=[operand])
```

If it's a new runtime function, add the implementation to `runtime/scratch_runtime.h`:

```c
static inline long scratch_round(long n) {
    return n;  /* Already an integer in our type system */
}
```

### Step 3: Write a test

Add a fixture to `tests/conftest.py` and a test to the appropriate test file. A minimal test:

```python
def test_my_new_opcode(self):
    project_json = {
        "targets": [{
            "isStage": True, "name": "Stage",
            "variables": {},
            "blocks": {
                "hat": {
                    "opcode": "event_whenflagclicked",
                    "next": "myblock",
                    "parent": None, "inputs": {}, "fields": {},
                    "shadow": False, "topLevel": True,
                },
                "myblock": {
                    "opcode": "sensing_askandwait",
                    "next": None,
                    "parent": "hat",
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
```

### Step 4: Run the tests

```bash
make test
```

## How to add a new code generation backend

1. Create `scratch2c/codegen/mybackend.py`
2. Subclass `CodegenBackend` from `base.py`
3. Implement all abstract methods (see `userspace.py` for a complete example)
4. Register it in `scratch2c/codegen/__init__.py`:

```python
from .mybackend import MyBackend

BACKENDS: dict[str, type[CodegenBackend]] = {
    "userspace": UserspaceBackend,
    "kernel": KernelBackend,
    "mybackend": MyBackend,        # ← add this
}
```

5. Add `"mybackend"` to the `choices` list in `scratch2c/cli.py`

## Code style

- Python 3.10+, type hints everywhere
- Dataclasses for data, functions for behavior
- Every public function gets a docstring
- Use `NOTE:` comments for known limitations or deliberate simplifications

## Running tests

```bash
uv sync              # Install everything (first time)
make test            # Run all tests
make coverage        # Run with coverage report
make lint            # Type-check with mypy
make example-fib     # See the Fibonacci example output
```
