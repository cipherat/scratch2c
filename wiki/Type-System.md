# Type System

Scratch is dynamically typed — any variable can hold a number or string at runtime. C is statically typed. The type inference pass resolves this gap by scanning how each variable is used and picking a type.

## Types

```python
class ScratchType(Enum):
    UNKNOWN = auto()  # not yet resolved
    LONG = auto()     # C long — 64-bit integer
    STRING = auto()   # C char[256] — fixed-size buffer
```

Floats are not supported. Scratch uses IEEE 754 doubles internally, but for the text/systems programs this tool targets, `long` is sufficient. See [[Known Limitations]].

## Two-pass algorithm

### Pass 1 — Assignment scanning

`_scan_statements()` walks every statement and looks at **what values are assigned** to each variable:

- `SetVariable` where the value is arithmetic → `LONG`
- `SetVariable` where the value is `scratch_join()` → `STRING`
- `SetVariable` where the value is a non-numeric string literal → `STRING`
- `SetVariable` where the value is `scratch_contains()` → `LONG`
- `ChangeVariable` (always numeric) → `LONG`

**Conflict resolution**: if a variable is assigned both numeric and string values, `STRING` wins. A `char[256]` can hold `"42"` just fine; a `long` can't hold `"hello"`.

### Pass 2 — Context propagation

`_propagate_statements()` looks at **where variables are used**:

- Variable used in `operator_add` → pin as `LONG`
- Variable used in `scratch_join` → pin as `STRING`
- Variable used in a comparison → pin as `LONG`

This resolves variables that Pass 1 couldn't classify (e.g., a variable that's only read, never assigned).

### Final default

After both passes, any variable still `UNKNOWN` defaults to `LONG`. This matches Scratch's behavior for uninitialized variables (they default to `0`).

## How types affect code generation

| Aspect | LONG | STRING |
|--------|------|--------|
| Declaration | `long x = 0;` | `char x[256] = "";` |
| Assignment | `x = value;` | `snprintf(x, sizeof(x), "%s", value);` |
| Say/print | `printf("%ld\n", x)` | `printf("%s\n", x)` |
| Used in arithmetic | `x` (direct) | `atol(x)` |
| Used in join/say | `scratch_ltoa(x)` | `x` (direct) |

## Adding type awareness for new functions

When you add a new `CallExpr` function (like `scratch_contains`), you need to register its return type in three places:

```python
# 1. type_inference.py → _classify_expression()
if expr.func in ("scratch_strlen", "scratch_contains"):
    return ScratchType.LONG

# 2. type_inference.py → _propagate_expr_context()
elif expr.func == "scratch_contains":
    for arg in expr.args:
        _propagate_expr_context(arg, ScratchType.STRING, variables)

# 3. codegen/base.py → _expr_type()
if expr.func in ("scratch_strlen", "scratch_contains"):
    return ScratchType.LONG
```

Missing any of these causes incorrect type inference or wrong format specifiers in the output.
