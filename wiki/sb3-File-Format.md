# sb3 File Format

An `.sb3` file is a ZIP archive containing `project.json` and media assets (images, sounds). We only use `project.json`.

## Targets

The JSON has a top-level `targets` array. Each target is a Stage or a Sprite:

```json
{
  "targets": [
    { "isStage": true, "name": "Stage", "variables": {...}, "blocks": {} },
    { "isStage": false, "name": "Sprite1", "variables": {}, "blocks": {...} }
  ]
}
```

**Variables on the Stage are global** — accessible from any sprite's code. Variables on a sprite are local to that sprite. Most simple projects define all variables on Stage and put all code on Sprite1. The transpiler flattens all variables into a single global scope via `Project.all_variables()`.

## Variables

```json
"variables": {
  "=7OuOX!=cDH{ozu~j]4(": ["f_0", 55],
  "ak@+oOZ@Fw~f[U-AUt![": ["b_1", true]
}
```

Keys are random IDs. Values are `[name, current_value]`. The current value is a **runtime snapshot** — whatever the variable held when the user last saved — not necessarily the initial value from the program logic. JSON `true`/`false` appear here for boolean variables; the IR builder normalizes them to `"1"`/`"0"` via `_normalize_value()`.

## Blocks

Scratch stores programs as a **flat dict of blocks** keyed by random IDs, linked by `next` and `parent` pointers:

```json
"blocks": {
  "abc123": {
    "opcode": "event_whenflagclicked",
    "next": "def456",
    "parent": null,
    "topLevel": true,
    "inputs": {},
    "fields": {}
  },
  "def456": {
    "opcode": "data_setvariableto",
    "next": null,
    "parent": "abc123",
    "inputs": { "VALUE": [1, [10, "42"]] },
    "fields": { "VARIABLE": ["my_var", "var_id_123"] }
  }
}
```

- **`opcode`**: what the block does. This is the primary dispatch key.
- **`next`**: ID of the block that follows (statement chaining). `null` = end of chain.
- **`parent`**: ID of the containing/preceding block.
- **`topLevel`**: `true` for hat blocks and procedure definitions.
- **`inputs`**: sub-expressions, nested bodies, and literal values.
- **`fields`**: static values like variable names or broadcast names.

## Input encoding

This is the most complex part. An input is an array where the first element is a shadow type and the rest encode the value.

**Shadow types** (first element):

| Value | Meaning |
|-------|---------|
| 1 | Shadow only (default/fallback value) |
| 2 | No shadow, block reference (SUBSTACK, CONDITION) |
| 3 | Block obscuring shadow (reporter plugged into input, shadow as fallback) |

**Type tags** (first element of the inner array):

| Tag | Meaning | Example |
|-----|---------|---------|
| 4 | Number | `[1, [4, "42"]]` |
| 5 | Positive number | `[1, [5, "3.14"]]` |
| 6 | Positive integer | `[1, [6, "10"]]` |
| 7 | Integer | `[1, [7, "-5"]]` |
| 8 | Angle | `[1, [8, "90"]]` |
| 9 | Color | `[1, [9, "#ff0000"]]` |
| 10 | String | `[1, [10, "hello"]]` |
| 12 | Variable reporter | `[3, [12, "var_name", "var_id"], [10, ""]]` |
| 13 | Broadcast | `[1, [13, "message1"]]` |

**Tags 4-9 are numeric contexts.** The IR builder uses `_normalize_numeric_literal()` for these, which converts `"true"`/`"false"` to `"1"`/`"0"` because the tag explicitly says "this is a number".

**Tag 10 is a string context.** The value is user-typed text. `"true"` under tag 10 is the string "true", not a boolean. The IR builder uses `_normalize_value()` for this, which passes strings through unchanged.

This distinction matters — see [[Known Limitations]] for the tag 10 ambiguity discussion.

**Block references** use the shadow type to point at another block:

```json
"VALUE": [3, "block_id_of_reporter", [10, "fallback"]]
```

Here `value_part` (index 1) is a string. If it exists as a key in the blocks dict, the IR builder follows it to build a sub-expression. The third element is the shadow fallback.

**SUBSTACKs** are nested statement bodies:

```json
"SUBSTACK": [2, "first_block_id_of_body"]
```

The IR builder follows the chain starting at that block ID via `_build_body()`.

## Procedures

Custom blocks use `procedures_definition` → `procedures_prototype` with a `mutation` object:

```json
"mutation": {
  "proccode": "greet %s",
  "argumentids": "[\"arg1_id\"]",
  "argumentnames": "[\"name\"]",
  "argumentdefaults": "[\"false\"]",
  "warp": "false"
}
```

Note: `argumentids` and `argumentnames` are **JSON strings containing JSON arrays** — they need a second `json.loads()`.

The `proccode` contains `%s` (string/number arg) and `%b` (boolean arg) placeholders. The IR builder strips these to derive C function names.

`procedures_call` blocks have the same `mutation` and use argument IDs as input keys.

## Variable reporters

Variables in expressions appear in two ways:

1. As a block with opcode `data_variable` and a `VARIABLE` field
2. As a shorthand `[12, "name", "var_id"]` directly in an input array

The IR builder handles both — `_resolve_input()` checks for shorthand arrays, `_build_expression()` handles `data_variable` blocks. Both produce `VariableRef` in the IR.

## Inspecting a project

```bash
unzip -o project.sb3 project.json
python3 -c "import json; print(json.dumps(json.load(open('project.json')), indent=2))"
```

Or use `--dump-ir` to see the parsed representation:

```bash
uv run scratch2c project.sb3 --dump-ir 2>&1
```
