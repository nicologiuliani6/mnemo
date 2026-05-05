# Mnemo C Runtime Minimal Spec

This document defines the current runtime contract for C parity tests in
`c_examples/gcc_compat`.

## Scope

- Goal: keep C syntax near `gcc -std=c11` while runtime library support is
  intentionally partial.
- Non-goal: full libc ABI compatibility.

## Supported runtime API (current baseline)

- `int printf(const char *fmt, ...)`
- `void *malloc(size_t n)`
- `void free(void *p)`

Compatibility header:
- `c_examples/gcc_compat/compat_runtime.h`

## printf formats currently accepted by Mnemo tests

- `%c`
- `%d`
- `%i`
- `%s`
- `%%`

Formats like `%u`, `%x`, `%p` are planned but not baseline-compatible yet.

## Quality gate used by gcc_compat runner

Runner: `c_examples/gcc_compat/run_compare.py`

A test is considered passing only if all are true:

1. Mnemo run succeeds (no VM/runtime crash).
2. GCC compile succeeds with **no warnings**.
3. Exit code matches between Mnemo and GCC execution.
4. Normalized stdout matches exactly.

## Planned expansion order

1. `printf` `%u`
2. `printf` `%x`
3. `printf` `%p`
4. additional C library surface as requested by parity roadmap
