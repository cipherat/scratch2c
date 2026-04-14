# Code Generation

Code generation uses the template method pattern: a base class walks the IR tree, and backend subclasses override target-specific methods.

## Base class (`codegen/base.py`)

`CodegenBackend` provides the full tree-walking logic. Its `generate(project)` method:

1. Emits file header (includes, module metadata)
2. Declares global variables based on inferred types
3. Emits forward declarations and procedure definitions
4. Groups scripts by hat kind:
   - `FLAG_CLICKED` / `BROADCAST_INIT` → init function body
   - `BROADCAST_EXIT` → exit function body
   - `BROADCAST_OTHER` → standalone named functions
5. Emits init function, exit function, file footer

## Backend interface

Subclasses override these methods:

```python
class MyBackend(CodegenBackend):
    def file_header(self) -> list[str]: ...
    def file_footer(self) -> list[str]: ...
    def emit_say(self, expr_code: str, is_string: bool) -> str: ...
    def main_signature_open(self) -> str: ...
    def main_signature_close(self) -> str: ...
    def exit_signature_open(self) -> str: ...
    def exit_signature_close(self) -> str: ...
    def declare_long_variable(self, c_name: str, initial: str) -> str: ...
    def declare_string_variable(self, c_name: str, initial: str) -> str: ...
    def wait_comment(self, duration_code: str) -> str: ...
```

Optional overrides:

```python
def emit_stop(self) -> str:     # default: "return;"
def _needs_exit(self) -> bool:  # default: False
```

## Userspace backend

Emits a standalone C program:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "scratch_runtime.h"

long my_var = 0;

int main(void) {
    my_var = 42;
    printf("%ld\n", (long)my_var);
    return 0;
}
```

## Kernel backend

Emits a Linux kernel module:

```c
#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/string.h>
#include "scratch_runtime.h"

MODULE_LICENSE("GPL");
MODULE_AUTHOR("scratch2c");
MODULE_DESCRIPTION("Scratch project compiled to kernel module");

static long my_var = 0;

static int __init scratch_init(void) {
    my_var = 42;
    printk(KERN_INFO "%ld\n", (long)my_var);
    return 0;
}

static void __exit scratch_exit(void) {
}

module_init(scratch_init);
module_exit(scratch_exit);
```

Key differences: `static` variables, `printk` instead of `printf`, `module_init`/`module_exit` macros in the footer, `emit_stop()` returns `"return 0;"` (because `scratch_init` returns `int`), `_needs_exit()` returns `True` (kbuild requires it).

## Expression emitters

The base class has two expression emitters that handle type coercion:

`_emit_expr_as_long(expr, variables)` — emit in numeric context. If the expression is naturally a string, wraps it in `atol()`.

`_emit_expr_as_string(expr, variables)` — emit in string context. If the expression is naturally numeric, wraps it in `scratch_ltoa()`.

The `Say` statement dispatcher calls `_expr_type()` to determine the message type, then passes `is_string` to the backend's `emit_say()`. This avoids the backend having to guess from the C code text.

## Safety features

**Division zero-guard**: all `/` and `%` operations emit `((divisor) != 0 ? (dividend) / (divisor) : 0)`.

**Loop counter uniqueness**: nested `Repeat` blocks use `_i0`, `_i1`, `_i2` via `_loop_counter` to avoid shadowing.

**Name sanitization**: `_c_varname()` converts Scratch names to valid C identifiers, avoids C keywords by prefixing with `s_`.

## Backend registry

Backends are registered in `codegen/__init__.py`:

```python
BACKENDS: dict[str, type[CodegenBackend]] = {
    "userspace": UserspaceBackend,
    "kernel": KernelBackend,
}
```

`get_backend("userspace")` returns an instance. See [[Adding Backends]] for how to add new targets.
