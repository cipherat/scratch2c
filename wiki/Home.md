# scratch2c Wiki

scratch2c transpiles MIT Scratch 3 projects (`.sb3` files) into compilable C code targeting userspace programs or Linux kernel modules.

## Pages

- [[Getting Started]] — Install, run, compile your first project
- [[Architecture]] — How the pipeline works, stage by stage
- [[sb3 File Format]] — How Scratch encodes programs in `project.json`
- [[Intermediate Representation]] — The IR dataclasses that connect parsing to codegen
- [[Type System]] — How dynamic Scratch types become static C types
- [[Code Generation]] — How the IR becomes C, and how backends work
- [[Runtime Library]] — `scratch_runtime.h` function reference and design
- [[Adding Opcodes]] — How to support a new Scratch block
- [[Adding Backends]] — How to add a new compilation target
- [[Troubleshooting]] — Debugging the pipeline when output is wrong
- [[Known Limitations]] — What doesn't work and why
