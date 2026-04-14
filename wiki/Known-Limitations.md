# Known Limitations

## No lists

Scratch lists would require dynamic arrays in C. Options include fixed-size arrays (simple but limited), `malloc`/`realloc` (complex in kernel space), or VLAs (stack-limited). This would need: a `List` IR node, handlers for `data_addtolist` / `data_deleteoflist` / `data_itemoflist` / `data_lengthoflist`, and a `scratch_list_*` family in the runtime header.

## No concurrency

Scratch runs multiple scripts in parallel via cooperative green threading. We emit them sequentially in the order they appear. For userspace, `pthreads` could work. For kernel, `kthreads` or workqueues. But this fundamentally changes the execution model and isn't planned.

## Procedure arguments are always `long`

The procedure signature is `void proc_name(long arg1, long arg2)`. If a procedure is called with a string argument, it gets `atol()`'d. A proper fix would need per-argument type inference or tagged unions.

## No clone/sprite interaction

Multi-sprite programs are flattened — all scripts from all sprites are merged into one file. Cloning, sprite-to-sprite messaging, and multi-sprite coordination are not supported.

## Float truncation

Scratch uses IEEE 754 doubles internally. We use `long`. Programs relying on fractional values (e.g., `set x to 3.14`) truncate to `3`. Supporting `double` would be straightforward but adds complexity to the type system and the type inference conflict resolution.

## Userspace exit handler not auto-called

Exit broadcast scripts in userspace go to a `void cleanup(void)` function that is defined but never called. It should either be invoked before `return 0;` in `main`, or registered with `atexit(cleanup)`.

## Stale initial values

The `.sb3` file saves variable values from the last runtime snapshot, not the initial values from the program logic. So you may see `static long f_0 = 55;` when the program immediately sets `f_0 = 0;`. Harmless but confusing. A cleanup pass could detect variables unconditionally assigned before first use and suppress the stale initializer.

## Tag 10 boolean ambiguity

Scratch's `set variable to` input field always uses type tag 10 (string literal) regardless of what the user types. This means there is no syntactic distinction in the `.sb3` file between a user who typed the word "true" and one who intended a boolean value.

In practice this rarely matters because Scratch has no boolean literal blocks. Booleans come from reporter blocks (`<contains>`, `<and>`, `<not>`, etc.) which produce separate expression nodes in the IR. A user who wants a boolean value would drag a reporter block into the input, producing a block reference — not a tag 10 string.

The transpiler handles this correctly:

- **Tags 4-9** (numeric context): `"true"` → `"1"`, via `_normalize_numeric_literal()`.
- **Tag 10** (string context): `"true"` stays as the string `"true"`. If assigned to a LONG variable, codegen emits `atol("true")` → `0`, matching Scratch's own `Number("true")` behavior.
- **JSON booleans** in variable initial values: Python `True`/`False` → `"1"`/`"0"` via `_normalize_value()`.

If a user expects `set var to "true"` (typed text) to mean boolean 1, the correct fix is to use a boolean reporter block in the Scratch project, not to add special-case handling in the transpiler.

## Missing opcodes

Many Scratch opcodes are not yet implemented. The IR builder silently skips unknown statement opcodes and returns `Literal(value="0")` for unknown expression opcodes. Use `--dump-ir` to identify which opcodes are dropping to fallback values. See [[Adding Opcodes]] for how to add support.

Currently unsupported categories include: lists, sensing (ask/answer, mouse, keyboard, timer), motion, looks (costume, backdrop, size, effects), sound, pen, and clone blocks.
