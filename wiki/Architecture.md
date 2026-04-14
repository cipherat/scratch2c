# Architecture

scratch2c is a four-stage pipeline. Each stage has a clear input and output, and each can be tested independently.

## Pipeline

```
.sb3 → reader.py → dict → ir_builder.py → IR → type_inference.py → IR (typed) → codegen → C source
```

**Stage 1 — Reader** (`scratch2c/reader.py`): opens the `.sb3` ZIP, extracts `project.json`, returns a Python dict. Also accepts raw JSON files for testing. No interpretation happens here.

**Stage 2 — IR Builder** (`scratch2c/ir_builder.py`): walks the flat block graph in the JSON dict and constructs a tree of Python dataclasses (the IR). This is where Scratch's linked-list-of-blocks encoding becomes structured statements and expressions. See [[Intermediate Representation]] and [[sb3 File Format]].

**Stage 3 — Type Inference** (`scratch2c/type_inference.py`): scans the IR and classifies every variable as `LONG` or `STRING`. Mutates `Variable.inferred_type` in place. See [[Type System]].

**Stage 4 — Code Generation** (`scratch2c/codegen/`): walks the typed IR and emits C source code. Uses a base class with a shared tree walker and backend subclasses that override target-specific parts (printf vs printk, main vs module_init). See [[Code Generation]].

## Key design rules

**The IR is the contract.** Parsing knows nothing about C. Codegen knows nothing about Scratch's JSON. The IR sits between them and speaks neither language — it describes program semantics (set variable, repeat, say) without encoding how those semantics are implemented.

**Backends share a tree walker.** The `CodegenBackend` base class handles all statement and expression emission. Backends only override ~10 methods that define target-specific behavior. Adding a new target does not require duplicating any walking logic.

**Type tag information is consumed at parse time.** Scratch's input arrays carry type tags (4-9 for numeric, 10 for string, 12 for variable reporter). The IR builder uses these tags to normalize values — for example, `"true"` under tag 4 becomes `"1"` because the tag says "this is a number". By the time values reach the IR as `Literal` nodes, the tag is gone. Downstream stages cannot and should not try to reconstruct it. See [[sb3 File Format]] section "Input encoding" for details.

**Unknown opcodes are skipped, not crashed on.** If the IR builder encounters a block opcode it doesn't handle, it returns `None` (for statements) or `Literal(value="0")` (for expressions). This produces partial but compilable output rather than a crash. The `--dump-ir` flag helps identify which opcodes were dropped.

## File layout

```
scratch2c/
├── scratch2c/
│   ├── reader.py            Stage 1
│   ├── ir.py                IR dataclass definitions
│   ├── ir_builder.py        Stage 2
│   ├── type_inference.py    Stage 3
│   ├── codegen/
│   │   ├── base.py          Shared tree walker + expression emitters
│   │   ├── userspace.py     Stage 4: userspace backend
│   │   └── kernel.py        Stage 4: kernel module backend
│   ├── cli.py               CLI entry point
│   └── __main__.py          python -m scratch2c
├── runtime/
│   └── scratch_runtime.h    C runtime helpers
└── tests/
    ├── conftest.py          Shared fixtures
    └── test_*.py            Per-stage tests
```
