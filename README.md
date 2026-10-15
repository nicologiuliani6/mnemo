# Mnemo

**Try it now:** [nicologiuliani.site/docs/mnemo](https://nicologiuliani.site/docs/mnemo/#playground) — compile and run C with Mnemo in your browser, nothing to install.

Mnemo compiles a **subset of C** to [Kairos](https://github.com/nicologiuliani6/kairos), a reversible concurrent language. The C program becomes a Kairos program that can run forwards and **backwards**: every destructive assignment saves the lost value on a history stack, so the whole run stays invertible.

Mnemo emits pure Kairos only (no VM extensions) and aims to produce the same output and the same exit code as `gcc` on programs in the subset.

```c
#include <stdio.h>
int sq(int x) { return x * x; }
int main(void) {
    int a[4] = {1, 2, 3, 4};
    int s = 0;
    for (int i = 0; i < 4; i++) s += sq(a[i]);
    printf("%d\n", s);          /* 30 */
    return 0;
}
```

```bash
mnemo example.c              # 30
```

---

## Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [How it works](#how-it-works)
4. [The C subset](#the-c-subset)
5. [Parallelism and channels](#parallelism-and-channels)
6. [try / rollback](#try--rollback)
7. [Testing](#testing)
8. [Known differences from gcc](#known-differences-from-gcc)

---

## Installation

**Packages (recommended).** Every [Mnemo release](https://github.com/nicologiuliani6/mnemo/releases) ships Linux packages of the standalone `mnemo` app (no Python needed). It needs the `kairos` package from the [Kairos releases](https://github.com/nicologiuliani6/kairos/releases), which provides the VM, and `gcc`. One line installs both, Kairos first if it is missing (asks for the sudo password):

```bash
curl -fsSL https://github.com/nicologiuliani6/mnemo/releases/latest/download/install.sh | bash
```

Or by hand:

| Distribution | Install |
|---|---|
| Debian / Ubuntu | `sudo apt install ./kairos_<version>_amd64.deb ./mnemo_<version>_amd64.deb` |
| Fedora / RHEL | `sudo dnf install ./kairos-<version>-1.<dist>.x86_64.rpm ./mnemo-<version>-1.<dist>.x86_64.rpm` |
| Arch Linux | `sudo pacman -U ./kairos-<version>-1-x86_64.pkg.tar.zst ./mnemo-<version>-1-x86_64.pkg.tar.zst` |

The package installs `/usr/local/bin/mnemo` (link to `/opt/mnemo/mnemo`); `mnemo prog.c` uses the installed `kairos` and `mnemo compile` links against `/usr/local/lib/kairos/libvm.so`.

**From source.** Clone the Kairos repository next to Mnemo (default `../kairos`, or `KAIROS_ROOT=/path`) and build it:

```bash
git clone https://github.com/nicologiuliani6/kairos.git
git clone https://github.com/nicologiuliani6/mnemo.git
(cd kairos && make install-deps && make)
cd mnemo && make venv          # .venv + pip install -e .
```

Each release also ships a wheel: `pip install mnemo-<version>-py3-none-any.whl`. `packaging/linux/build.sh deb|rpm|arch` builds the Linux packages locally.

Requirements: Python ≥ 3.10, `gcc` (also used as the preprocessor), `make`.

| Variable | Default | Effect |
|---|---|---|
| `KAIROS_ROOT` / `MNEMO_KAIROS_ROOT` | `../kairos` | Kairos repository used to run programs |
| `MNEMO_KAIROS` | `kairos` | Kairos app used when there is no Kairos repository (`mnemo prog.c --kairos PATH` overrides it) |

---

## Usage

```bash
mnemo prog.c [options]                         # compile to .kairos and run (same as `mnemo run prog.c`)
mnemo dump-kairos prog.c [-o out.kairos] [--stdout]
mnemo compile prog.c [-o exe] [--keep-kairos]   # native executable: bytecode + libvm.so, no Python
```

`mnemo prog.c` (or `mnemo run prog.c`) prints the program's output and exits with the value returned by `main`, like `kairos prog.kairos`.

| Option | Effect |
|---|---|
| `--main-argc N` | value of `argc` (otherwise the `// mnemo-main-argc: N` directive, otherwise 0) |
| `--opt-uncall-user-calls` | after each eligible call, frees its history (see below) |
| `--check-invertibility` | runs `main` and then inverts it: the VM reports every non-invertible step |
| `--auto` (when running) | decides by itself whether to enable `--opt-uncall-user-calls` |
| `--vm-dump`, `--vm-stats` (when running) | print the final VM dump / how many cells are still alive |
| `--kairos PATH` (when running) | Kairos executable to use |
| `-v` | commands and exit codes on stderr |

---

## How it works

```
prog.c ─ gcc -E -DMNEMO ─ pycparser ─▶ AST
      ─ rewrites (early returns, switch, static, stdlib…)
      ─ layout_collect.py   one memory cell per variable, array, field
      ─ c_lower.py          AST → IR (reversible assignments, history, if/from)
      ─ arrayize.py         cells → Kairos array __mn_mem
      ─ prelude.py + mnemo/lib/   library procedures (printing, bits, division…)
      ─ emit_kairos.py      IR → .kairos text ─▶ Kairos VM
```

### Reversibility

C destroys information (`x = 5` loses the old `x`); Kairos does not. Mnemo writes every assignment as `push(x, __mn_hist); x += 5`: the old value goes to the history stack `__mn_hist`, temporaries to `__mn_scratch`. Running backwards pops them again. Control flow becomes Kairos `if … fi` and `from … until` with the exit assertions the inverse needs, and every `local` is closed by a `delocal` in the same block, as Kairos (like Janus) requires.

### Memory

All the program's named state (scalars, arrays, structs, globals) and the first part of the `malloc` heap live in a single Kairos array `int __mn_mem[N]`; a pointer is an index. Procedures receive the array by reference; `a[i]` with a run-time index becomes a direct access `__mn_mem[(base + i)]`, `*p` a direct access to the array or to the tape.

The heap is unbounded. Its first part sits at the end of the array (size inferred from the source's `malloc`s, at least 1024 cells if the program uses any). Kairos arrays cannot grow, so past the end of the array the heap continues on a **tape** made of two Kairos stacks with a cursor between them: there an access costs the distance from the previous access (walking a block is O(1) per cell, long jumps cost more) and the tape grows by itself. `free` only reuses the most recently allocated block.

### `--opt-uncall-user-calls`

The history grows with every assignment. With this option, after `call f(…)` Mnemo saves the cells written by `f`, runs `uncall f` (which empties the history produced by `f`) and puts the results back with an XOR swap: same result, much less memory on long programs. Excluded: direct recursion, functions with channels or `par`, and functions that write through pointer parameters outside loops.

### Kairos libraries (`mnemo/lib/`)

Included automatically when needed: `putd`/`putx`/`puto` (printing integers in base 10/16/8, with width and padding), `bits` (`&`, `|`, `<<`, `>>`), `divmod`, `mul`, `mod`, `helpers` (32-bit mask for `unsigned`). `* / %` are native Kairos operators.

---

## The C subset

**Types.** `int`, `unsigned`, `char` (including 8-bit arithmetic), `bool`/`_Bool`, `short`/`long`/`long long` (as `int`), `size_t`, `int*_t`/`uint*_t`, `enum`, `struct`, `union` (nested too), `typedef`. No floating point.

**Pointers.** `void *`, multi-level pointers (`int **`), arithmetic (`p + i`, `p++`, `q - p`), `&x`, `&s.field`, `&a[i]`, pointers to structs and to matrix rows (`int (*r)[N]`), `malloc`/`calloc`/`free`.

**Arrays.** Multidimensional, initialisers (designated too), run-time indices, passing to functions as pointers. No VLAs.

**Control flow.** `if`, `switch` (body inside `{}`), `while`, `do`, `for`, `break`, `continue`, `return` anywhere, ternary operator, short-circuit `&&`/`||`, `_Generic`. No `goto`, `setjmp`, `_Atomic`, asm, bit-fields.

**Functions.** Recursion (mutual too), `struct` by value and as return value, function pointers (assigned, in arrays with run-time index, as parameters, as struct fields, returned by functions). `main` is `void`, `int argc` or `int argc, char **argv` (`argv` is syntactic only). No user-defined variadic functions.

**Strings.** `char *` from literals (reassigned and returned too), `char s[] = "…"`, `printf("%s", …)`.

**Standard library** (many functions are evaluated at compile time on constant arguments):

| Header | Support |
|---|---|
| `stdio.h` | `printf` (`%d %i %u %x %X %o %c %s %p %%`, width, `-`, `0`, `l`/`ll`), `putchar`, `puts`, `sprintf`/`snprintf` on constant arguments; `fprintf`/`fputs`/`fputc` on `stdout` (silent on `stderr`); `fflush` & co. return 0 |
| `stdlib.h` | `malloc`, `calloc`, `free`, `abs`/`labs`/`llabs`, `div`/`ldiv`, `atoi`/`strtol`/`strtoul` on literals, `exit`/`abort` only in `main`, `getenv` → `NULL` |
| `string.h` | `strlen`, `strcmp`, `strncmp`, `strchr`, `strrchr`, `strstr`, `strspn`, `memcmp`, `memchr`, `strcpy`, `strcat`, `memcpy`, `memset`, `memmove`, `strdup`, `strerror` |
| `strings.h` | `bzero`, `bcopy`, `index`, `rindex`, `strcasecmp` |
| `stdarg.h` | `va_list`, `va_start`, `va_arg`, `va_end` |
| `time.h`, `locale.h` | `time`/`clock` → 0, `setlocale` → `NULL` |

Source directive: `// mnemo-main-argc: N`.

---

## Parallelism and channels

```c
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));
```

With two distinct functions this becomes a Kairos `par … and … rap`: two real threads. In Kairos the branches of a `par` share no writable memory, so the right branch works on its own memory window (`__mn_memR`, with a copy of the globals it reads). A global **written** by one branch and used by the other is a compile error: branches communicate only through channels. `parallel2(f, f)` with the same function runs sequentially. Variants: `mnemo_pthread_parallel_with(worker, cont)` and `mnemo_pthread_parallel_with1(worker, arg, cont)`.

Channels are Kairos's synchronous channels:

- `mnemo_kairos_channel_t` with `ssend`/`srecv`, including channel passing (see `tests/c/examples_advanced/pi_calculus.c` and `mnemo_kairos_pi.h`);
- the producer/consumer model of `tests/c/examples_advanced/mps.h`, where a `pthread_mutex_t lane` field acts as a channel.

`pthread_mutex_lock`/`unlock` on an actual mutex are **no-ops**: with no shared memory between branches there is nothing to protect, and a rendez-vous channel cannot act as a symmetric mutex. As a consequence, `printf`s from two parallel branches may interleave character by character.

---

## try / rollback

A Mnemo extension built on Kairos's `try`:

```c
try (x < 10) {
    x += step;           /* run forwards */
} rollback {
    attempts++;          /* if the condition is false: body undone, then this */
}
```

The condition, evaluated after the body, is a simple comparison; no `par` or channels in the body. Mnemo adds the `yrt` exit assertion itself (a flag the body sets, so it is true after a commit and false after a rollback) and then moves the flag to the history. Examples: `tests/c/repro/try_*.c`, `tests/c/examples_advanced/maze_backtrack.c`.

---

## Testing

| Command | What it does |
|---|---|
| `make test-unit` | Python tests (`tests/test_*.py`) |
| `make test` | compiles and runs `tests/c/examples/*.c` |
| `make test-gcc-compat` | 190 programs: stdout and exit code must match `gcc` (`COMPAT_ARGS='--category control'` to filter, `…-stop` to stop at the first failure) |
| `bash tests/c/probe/run.sh` | larger 1:1 comparison corpus against `gcc` |
| `make run FILE=prog.c` | a single file |
| `make clean-kairos` | removes the generated `.kairos` files |

`tests/c/repro/` holds the regression cases and a few larger projects (`encrypt.c`, `des.c`, `projects/`); `tests/c/examples_advanced/` the concurrent examples.

---

## Known differences from gcc

- `int` is 64-bit: signed overflow (undefined behaviour in C) does not wrap at 32 bits; `unsigned` does wrap correctly modulo 2³².
- `sizeof` a pointer is 4 (one cell).
- Call arguments are evaluated left to right.
- No real I/O (files, input), no signals, no `errno`.
- `printf`s from two `par` branches may interleave (see above).
