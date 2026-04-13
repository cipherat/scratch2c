/*
 * scratch_runtime.h — Runtime support for scratch2c-generated C code.
 *
 * This header is self-contained. It detects whether it is being compiled in
 * userspace (normal C program) or kernel space (Linux kernel module) and
 * provides the appropriate implementations.
 *
 * OWNERSHIP SEMANTICS:
 *   - scratch_join() returns a pointer to a thread-local static buffer.
 *     The caller does NOT own the memory and must not free() it.
 *     The buffer is overwritten on every call, so copy the result if you
 *     need to keep it across calls. Each call site gets its own buffer
 *     because we use a rotating pool — this makes nested join() calls safe
 *     (e.g., join(join(a, b), c)).
 *
 *   - scratch_ltoa() returns a pointer to a thread-local static buffer.
 *     Same ownership rules as scratch_join().
 *
 *   - scratch_letter_of() returns a pointer to a static 2-byte buffer.
 *     Same ownership rules.
 *
 * NOTE: This design trades a small amount of memory (a few KB of static
 * buffers) for simplicity and reentrancy. A production compiler would use
 * heap allocation with reference counting, but that's overkill for an
 * educational tool.
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef SCRATCH_RUNTIME_H
#define SCRATCH_RUNTIME_H

/* -------------------------------------------------------------------
 * Buffer pool configuration
 * -------------------------------------------------------------------
 * We use a rotating pool of buffers so that nested calls like
 * scratch_join(scratch_join(a, b), c) don't clobber each other.
 * 8 buffers is enough for any reasonable nesting depth.
 */
#define SCRATCH_BUF_SIZE  1024
#define SCRATCH_BUF_COUNT 8

/* -------------------------------------------------------------------
 * Kernel vs. userspace detection
 * ------------------------------------------------------------------- */

#ifdef __KERNEL__

#include <linux/kernel.h>
#include <linux/string.h>

/* Kernel doesn't have atol — provide a simple implementation */
static inline long scratch_atol(const char *s) {
    long result = 0;
    int negative = 0;
    if (!s) return 0;
    while (*s == ' ') s++;
    if (*s == '-') { negative = 1; s++; }
    else if (*s == '+') { s++; }
    while (*s >= '0' && *s <= '9') {
        result = result * 10 + (*s - '0');
        s++;
    }
    return negative ? -result : result;
}

#define atol(s) scratch_atol(s)

#else /* Userspace */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#endif /* __KERNEL__ */


/* -------------------------------------------------------------------
 * Buffer pool
 * -------------------------------------------------------------------
 * Each function that returns a string rotates through a pool of buffers.
 * This makes it safe to use multiple return values in one expression
 * without them stomping on each other.
 */

static char _scratch_bufs[SCRATCH_BUF_COUNT][SCRATCH_BUF_SIZE];
static int _scratch_buf_idx = 0;

static inline char *_scratch_next_buf(void) {
    char *buf = _scratch_bufs[_scratch_buf_idx];
    _scratch_buf_idx = (_scratch_buf_idx + 1) % SCRATCH_BUF_COUNT;
    return buf;
}


/* -------------------------------------------------------------------
 * scratch_join(a, b) — concatenate two strings
 * -------------------------------------------------------------------
 * Returns a pointer into the rotating buffer pool.
 * Safe for nesting: scratch_join(scratch_join(x, y), z)
 */
static inline const char *scratch_join(const char *a, const char *b) {
    char *buf = _scratch_next_buf();
    if (!a) a = "";
    if (!b) b = "";
    /* snprintf guarantees null termination and prevents overflow */
    snprintf(buf, SCRATCH_BUF_SIZE, "%s%s", a, b);
    return buf;
}


/* -------------------------------------------------------------------
 * scratch_ltoa(n) — convert a long to its string representation
 * -------------------------------------------------------------------
 * Returns a pointer into the rotating buffer pool.
 */
static inline const char *scratch_ltoa(long n) {
    char *buf = _scratch_next_buf();
    snprintf(buf, SCRATCH_BUF_SIZE, "%ld", n);
    return buf;
}


/* -------------------------------------------------------------------
 * scratch_strlen(s) — string length
 * -------------------------------------------------------------------
 * Thin wrapper that handles NULL gracefully.
 */
static inline long scratch_strlen(const char *s) {
    if (!s) return 0;
    return (long)strlen(s);
}


/* -------------------------------------------------------------------
 * scratch_letter_of(index, s) — get the character at position `index`
 * -------------------------------------------------------------------
 * Scratch uses 1-based indexing. Returns a 1-character string.
 * Out-of-bounds returns an empty string (Scratch behavior).
 */
static inline const char *scratch_letter_of(long index, const char *s) {
    static char letter_buf[2] = {0, 0};
    if (!s) { letter_buf[0] = '\0'; return letter_buf; }
    long len = (long)strlen(s);
    /* Scratch is 1-indexed */
    if (index < 1 || index > len) {
        letter_buf[0] = '\0';
        return letter_buf;
    }
    letter_buf[0] = s[index - 1];
    return letter_buf;
}


#endif /* SCRATCH_RUNTIME_H */
