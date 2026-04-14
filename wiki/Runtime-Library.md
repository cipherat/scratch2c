# Runtime Library

`runtime/scratch_runtime.h` is a self-contained C header included by all generated code. It detects `__KERNEL__` at compile time and provides appropriate implementations for both userspace and kernel space.

## Buffer pool

String-returning functions (`scratch_join`, `scratch_ltoa`, `scratch_letter_of`) need somewhere to put the result. We use a rotating pool of 8 static buffers:

```c
#define SCRATCH_BUF_SIZE  1024
#define SCRATCH_BUF_COUNT 8

static char _scratch_bufs[SCRATCH_BUF_COUNT][SCRATCH_BUF_SIZE];
static int _scratch_buf_idx = 0;
```

Each call to a string-returning function takes the next buffer in the pool. This makes nested calls safe — `scratch_join(scratch_join("a", "b"), "c")` uses buffer 0 for the inner call and buffer 1 for the outer, so they don't clobber each other.

**Ownership**: the caller does NOT own the returned pointer. The buffer is overwritten on the next call cycle. To keep a result, copy it:

```c
// Generated code does this for STRING variable assignment:
snprintf(my_var, sizeof(my_var), "%s", scratch_join("hello ", "world"));
```

## Function reference

### `scratch_join(a, b)`

Concatenates two strings. NULL-safe (NULL → "").

```c
const char *scratch_join(const char *a, const char *b);
// scratch_join("hello ", "world") → "hello world"
```

### `scratch_ltoa(n)`

Converts a long to its string representation.

```c
const char *scratch_ltoa(long n);
// scratch_ltoa(42) → "42"
```

### `scratch_strlen(s)`

Returns string length. NULL-safe (NULL → 0).

```c
long scratch_strlen(const char *s);
// scratch_strlen("hello") → 5
```

### `scratch_letter_of(index, s)`

Returns the character at position `index` as a 1-character string. Scratch uses 1-based indexing. Out of bounds returns `""`.

```c
const char *scratch_letter_of(long index, const char *s);
// scratch_letter_of(1, "hello") → "h"
// scratch_letter_of(0, "hello") → ""
```

Note: uses a separate static buffer (not the pool) since it's always 2 bytes.

### `scratch_contains(haystack, needle)`

Case-insensitive substring check. Returns 1 if found, 0 otherwise. Empty needle returns 1 (Scratch behavior).

```c
long scratch_contains(const char *haystack, const char *needle);
// scratch_contains("Apple", "app") → 1
// scratch_contains("Apple", "z")   → 0
```

## Kernel compatibility

When `__KERNEL__` is defined:

- `<linux/kernel.h>` and `<linux/string.h>` replace `<stdio.h>`, `<stdlib.h>`, `<string.h>`
- `atol()` is provided as `scratch_atol()` since the kernel doesn't have the standard library version
- `snprintf` comes from `<linux/kernel.h>`

## Adding a new runtime function

1. Add the implementation to `scratch_runtime.h`
2. Use `static inline` and the buffer pool if it returns a string
3. Handle `NULL` inputs gracefully
4. Make it work under both `__KERNEL__` and userspace — avoid stdlib functions that don't exist in the kernel
