# TODO

## Status

Mnemo emits pure Kairos only (no VM extensions): memory as the Kairos array
`__mn_mem`, native `* / %`, no-op mutexes, `par` over disjoint memory windows.
Gates: `make test-gcc-compat` 190/190, `make test` 37/37, `make test-unit`
green, the `tests/c/probe` corpus (see the count in `run.sh`).

## Known limits (found by the corpus, non-trivial fix)

- **`printf("%s", buf)` with `buf` pointing to a HEAP buffer** (`malloc`):
  the `%s` dispatch only matches known static strings (ROS/char[]); a heap
  buffer would need a reversible loop that reads `pool[buf+i]` up to the NUL
  and shows each byte. Static/literal strings and local `char[]` work.
  (repro `tests/c/probe/cases/p6_string_dup.c`).
- **Manual `realloc` in a loop** (new `malloc` + copy + `free` + reassigning the
  pointer, inside a loop): re-allocation semantics are hard to invert (see also
  `realloc` under "Not feasible"). The case outside a loop works.
  (repro `tests/c/probe/cases/p6_dyn_grow.c`).
- **`printf` from two `par` branches**: mutexes are no-ops (branches share no
  memory; a rendezvous channel is not a symmetric mutex). Each Kairos `show`
  prints its whole line, but a C `printf` becomes several `show`s, so the
  output of two branches can still interleave
  (`tests/c/examples_advanced/PC.c`).
- **Heap beyond the array**: past `__mn_mem` the heap lives on a tape of stacks
  (unbounded, access O(distance)); a malloc inside a `par` branch is not
  supported (explicit error: the heap belongs to the caller).
- **Slow access through array parameters**: summing a 1500-element array passed
  to a function is correct but takes minutes. To investigate.
- **union type punning int↔byte** (`union{int i;unsigned char b[4];}; u.i=…;
  u.b[k]`): the word model (1 cell = one 4-byte word) does not alias the
  sub-bytes; writing `u.i` does not fill `u.b[]`. "Tagged" unions (one member
  at a time, same width) work; byte-wise reinterpretation does not. (repro
  `tests/c/probe/cases/p8_union.c`).

## Divergences by design / undefined behaviour (not bugs)

- **`int` is 64-bit**: signed `int` overflow (UB in C) does not wrap at 32
  bits. `unsigned` does wrap correctly modulo 2^32.
- **`sizeof(T*)` = 4** (word model: a pointer is one cell).
- **Argument evaluation order** left to right (gcc x86-64: right to left);
  unspecified in C, it only shows with arguments that have side effects.

## Not feasible for a reversible model / the Kairos VM

Structurally excluded features: they will not be implemented while Mnemo
targets a reversible integer VM.

### They break reversibility

- **`goto`**: unstructured control flow, no inverse walk.
- **`setjmp` / `longjmp`**: stack unwinding is not reversible.
- **`exit(n)` outside main**: termination from an arbitrary stack depth is not reversible. (`exit(n)` INSIDE main is supported by rewriting it to `return n`.)
- **`abort()` outside main**: asynchronous termination is not reversible. (Inside main it is supported as `return 134`.)
- **`signal` / signal handlers**: asynchronous interrupts.
- **Inline asm** (`__asm__`, `asm volatile`): no IR.

### No floating point

The Kairos VM only works on integers. Excluded:

- **`float`, `double`, `long double`**.
- **`_Complex`** (C99 complex).
- **`<math.h>`** (sin, cos, sqrt, …).

### No real I/O / syscalls

The VM has no syscalls besides `printf`/`putchar`/`puts` (text output).

- **`scanf`, `getchar`, `fgets`**: no input.
- **`fopen`, `fprintf`, `fclose`, `fread`/`fwrite`**: no filesystem. (`fflush`/`feof`/`ferror`/`clearerr`/`setvbuf`/`fileno` return 0 through an AST rewrite, for syntactic compatibility.)
- **`<time.h>`**: no real clock/timer. (`time()`/`clock()` return 0 through an AST rewrite.)
- **`<unistd.h>`, `<sys/*>`**: no POSIX syscalls.
- **`<stdlib.h>` `system`**: running external processes. Only `malloc`/`calloc`/`free` (ptr pool). (atoi and getenv are supported: atoi at compile time, getenv returns NULL.)
- **`realloc`**: re-allocation semantics are hard to invert.
- **Setting/mutating `errno`**: unmodelled mutable global. Only *reading* errno is supported: the fake `<errno.h>` exposes `errno` as the int 0 (no syscalls, so never an error). E* constants are defined.
- **Real POSIX `argv`**: strings from the OS are not available (syntactic stub).

### Non-π concurrency

The VM only has π-calculus channels as a synchronization primitive. Excluded:

- **`_Atomic`**: LL/SC memory-order semantics are not modelled.
- **`pthread_*`** in general: only `mnemo_pthread_parallel2`/`_with`/`_with1` (→ `par`) and `pthread_mutex_*` (no-op).

### Multiple translation units / linker

Mnemo is a single-file compiler. Excluded:

- **Multiple translation units** (`gcc a.c b.c -o`).
- **Cross-TU `extern`** (no global linker).
- **`#include` of user headers with definitions**: `gcc -E -DMNEMO` expands everything into one blob, but cross-file typedefs/structs can confuse the layout.

### GCC-specific

- **`__attribute__((…))`**: packed, aligned, used, weak, etc.
- **`__builtin_*`**: `__builtin_expect`, `__builtin_unreachable`, etc.
- **Nested function definitions** (GCC extension).

### VLAs

- **`int a[n]` with a runtime `n`**: the cell layout must be known at compile time for the PAR partition and the pointer pool.
