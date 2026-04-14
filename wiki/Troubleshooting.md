# Troubleshooting

## Debugging strategy

The pipeline is linear. When output is wrong, trace forward from the input until you find the stage where data breaks:

1. **Check the JSON**: `unzip -o project.sb3 project.json && python3 -c "import json; print(json.dumps(json.load(open('project.json')), indent=2))"`
2. **Check the IR**: `uv run scratch2c project.sb3 --dump-ir 2>&1`
3. **Check the C**: `uv run scratch2c project.sb3 --backend userspace`

If the JSON is correct but the IR is wrong → bug in `ir_builder.py`.
If the IR is correct but the C is wrong → bug in `codegen/` or `type_inference.py`.

## Common issues

### Variables are all zero

**Symptom**: all variables initialize to `0` regardless of what the Scratch project sets them to.

**Likely cause**: the `set variable to` blocks reference an expression block (like `operator_contains`) that the IR builder doesn't recognize. Unknown expression opcodes fall back to `Literal(value="0")`.

**How to find it**: run `--dump-ir` and look for `SetVariable` nodes whose `value` is `Literal(value='0')` when you expected something else. Then check the JSON to see what opcode the input block actually uses. See [[Adding Opcodes]].

### Garbage numbers in dmesg (kernel module)

**Symptom**: output like `-1041686496` instead of the expected string.

**Likely cause**: a `char[]` variable is being printed with `%ld` instead of `%s`. The `emit_say(expr_code, is_string)` method receives the wrong `is_string` flag, or `_expr_type()` doesn't recognize the expression as a string.

**How to verify**: look at the generated C. If you see `printk(KERN_INFO "%ld\n", (long)my_string_var)`, the type dispatch is wrong.

### No output from insmod

**Symptom**: `sudo insmod module.ko` succeeds but `dmesg` shows nothing.

**Check**: does the generated C have `module_init(scratch_init);` at the bottom? Without this macro, the kernel doesn't know which function to call on load.

### kbuild fails with "No such file or directory: Makefile"

**Cause**: kbuild needs a `Kbuild` file in the module source directory. The `make kbuild` target generates this automatically. If you're building manually, create `build/Kbuild` containing:

```
obj-m += your_module.o
```

### Variables from Stage not visible to Sprite1 code

This works correctly — `Project.all_variables()` flattens variables across all targets. If a variable is missing, check that its ID in the block's `VARIABLE` field matches an ID in some target's `variables` dict. Scratch uses the same IDs across targets for global variables.

### Procedure arguments are wrong

Procedure parameters are always typed as `long`. If a string argument is passed, it gets `atol()`'d. This is a [[Known Limitation|Known Limitations]]. Check `--dump-ir` to verify the `ProcedureCall.args` list matches what you expect.

## Running tests

```bash
uv run pytest tests/ -v              # all tests
uv run pytest tests/test_ir_builder.py -v   # just IR builder tests
uv run pytest -k "fibonacci" -v      # tests matching "fibonacci"
```

## Type-checking

```bash
uv run mypy scratch2c/
```
