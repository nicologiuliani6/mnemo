# Mnemo

Compilatore da un **subset reversibile di C** a **Kairos** (`.kairos`), il
linguaggio sorgente della VM reversibile [Kairos](https://github.com/nicologiuliani6/kairos).

Mnemo **non** vendora Kairos. Il repo Kairos deve esistere in `$KAIROS_ROOT`
(default `../kairos`), buildato con `make build-release`.

---

## Installazione

```bash
git clone https://github.com/nicologiuliani6/mnemo.git
git clone https://github.com/nicologiuliani6/kairos.git   # accanto a mnemo
cd kairos && make build-release && cd ../mnemo
make venv        # crea .venv + pip install -e .
```

Richiede: Python 3.10+, `gcc`, `make`. La VM Kairos viene compilata da C.

Variabili d'ambiente:

| Variabile               | Default        | Effetto                                                |
| ----------------------- | -------------- | ------------------------------------------------------ |
| `KAIROS_ROOT`           | `../kairos`    | Path repo Kairos                                       |
| `MNEMO_KAIROS_ROOT`     | =`KAIROS_ROOT` | Alias                                                  |
| `MNEMO_KAIROSAPP`       | `kairosapp`    | Override eseguibile runner                             |
| `KAIROS_NATIVE_ARITH=1` | off            | mul/div/mod/bitwise O(1) in C (anche `--native-arith`) |

---

## CLI

Dopo `pip install -e .` (o via `make venv`):

```bash
mnemo compile src.c [opzioni]      # → eseguibile nativo (bytecode + libvm.so)
mnemo dump-kairos src.c [-o out.kairos] [--stdout]
mnemo run src.c [opzioni]          # compila ed esegue
mnemo dump-ir src.c                # IR umano-leggibile
mnemo emit-kairos src.c            # solo .kairos su stdout
```

### Flag (validi per `compile`, `dump-kairos`, `run`)

| Flag                       | Default | Effetto                                                                                      |
| -------------------------- | ------- | -------------------------------------------------------------------------------------------- |
| `--main-argc N`            | 0       | `argc` iniziale per `main` (override `// mnemo-main-argc:`)                                  |
| `--ptr-pool-size N`        | 4       | Celle pool malloc/free (max 256). Fallback banked pools se serve.                            |
| `--arr-max N`              | 1024    | Limite elementi per array (max 65536)                                                        |
| `--opt-uncall-user-calls`  | off     | Per ogni `call f(...)` eligible: snapshot XOR + uncall + swap (frees Kairos stacks)          |
| `--check-invertibility`    | off     | Wrappa `main` in proc + `call __main__ ; uncall __main__` per verificare reversibilità 100%  |
| `--keep-kairos`            | off     | (solo `compile`) Scrive anche `stem.kairos` accanto al `.c`                                  |
| `-v`/`--verbose`           | off     | Log su stderr                                                                                |

### Flag solo `run`

| Flag             | Effetto                                                              |
| ---------------- | -------------------------------------------------------------------- |
| `--kairosapp P`  | Override runner (default `$MNEMO_KAIROSAPP` o `kairosapp`)           |
| `--native-arith` | `KAIROS_NATIVE_ARITH=1` nella VM                                     |
| `--vm-dump`      | Stampa anche il blocco dump della VM (default off)                   |
| `--vm-stats`     | Stampa `mean_abs` + `max_abs` dei cell int post-execution            |

---

## Subset C supportato

**Tipi scalari**: `int`, `unsigned`, `bool`/`_Bool`, `char` (variabile +
literal), `short`/`long`/`long long` (alias a `int`), `size_t`,
`int*_t`/`uint*_t` (via `mnemo/fake_include/`).

**No** floating-point (`float`/`double`/`_Complex`/`<math.h>`).

**Puntatori**: indici in pool. `void *`, multi-level `int **p`, aritmetica
`p+i`, `p++`, `*(p+i)`, `q-p` su array. `&id` e `&struct.field` ammessi.

**Strutture**: `struct`, `union`, `enum`, bit-field NO, `__attribute__` NO.

**Controllo**: `if`/`else`, `switch`/`case` (body `{...}`), `while`, `do`,
`for`. **No** `goto`, `setjmp`/`longjmp`, `_Atomic`, inline asm, VLA.

**Funzioni**: function pointer solo compile-time-resolved (`p = f`,
`&f`, `f` stesso file). No variadic user-defined. `main` accetta `void`,
`int argc`, o `int argc, char **argv` (argv stub sintattico).

**Parallelismo**: `mnemo_pthread_parallel2(a, b)` con 2 worker distinti
emette `par ... and ... rap`. `pthread_mutex_t` lowered a channel
π-calcolo. Vedi `mps.h` per pattern producer/consumer.

### Librerie standard supportate

#### `<stdlib.h>`
- `malloc(n)` / `free(p)` — ptr_pool reversibile.
- `exit(N)` / `abort()` — solo dentro `main`. AST rewrite a `return N`
  (`abort` → `return 134` = 128+SIGABRT).
- `getenv(X)` — AST rewrite a `NULL` (VM no env).
- `abs` / `labs` / `llabs` — AST rewrite a ternario.
- `div` / `ldiv` / `lldiv` — AST rewrite a compound literal `(T){a/b, a%b}`.
- `atoi` / `atol` / `atoll` — compile-time su string literal.
- `strtol` / `strtoul` / `strtoll` / `strtoull` — compile-time, supporta
  base 0/8/10/16 e prefissi `0x`/`0`.

#### `<string.h>`
- `strlen` / `strnlen` — compile-time su literal.
- `strcmp` / `strncmp` / `memcmp` — compile-time, byte-diff glibc semantics.
- `strcasecmp` / `strncasecmp` — compile-time case-insensitive.
- `strchr` / `strrchr` / `strstr` / `strpbrk` — AST rewrite a sub-literal/NULL.
- `strspn` / `strcspn` — char-class compile-time.
- `strdup` — AST rewrite a literal.
- `memchr` — AST rewrite a sub-literal/NULL.
- `memcpy` / `memset` / `memmove` — compile-time su dst array Mnemo.
- `strcpy` / `strncpy` — compile-time.
- `strcat` / `strncat` — runtime byte append reversibile (dst char[] Mnemo,
  src string literal).
- `strerror(N)` — compile-time lookup → string literal glibc.

#### `<strings.h>` (POSIX legacy)
- `bzero` → `memset(p, 0, n)`.
- `bcopy(src, dst, n)` → `memmove(dst, src, n)`.
- `index` / `rindex` → alias di `strchr` / `strrchr`.

#### `<stdio.h>`
- `printf` / `putchar` / `puts` — runtime (auto-include `putd.kairos` per `%d`).
- `sprintf` / `snprintf` — compile-time fmt parsing. Supporta
  `%d %u %x %llx %X %o %s %c %%` + flag/width. Args costanti.
- `printf` `%X` / `%llX` — uppercase hex, solo argomenti costanti.
- `fflush` / `setvbuf` / `setbuf` / `feof` / `ferror` / `clearerr` /
  `fileno` — AST rewrite a `0` (VM no FS).
- `fputs(s, stdout)` → `printf("%s", s)`, `fputc(c, stdout)` →
  `putchar(c)`, `fprintf(stdout, fmt, ...)` → `printf(fmt, ...)`.
  Su `stderr` diventano no-op (output silente).

#### `<time.h>`
- `time(t)` / `clock()` — AST rewrite a `0` (VM no clock).

#### `<locale.h>`
- `setlocale(cat, name)` — AST rewrite a `NULL` (VM no locale).
- Costanti `LC_ALL`/`LC_COLLATE`/`LC_CTYPE`/etc. definite.

#### `<pthread.h>` (subset Mnemo)
- `mnemo_pthread_parallel2(a, b)` — 2 worker → `par`/`rap`.
- `pthread_mutex_t` / `pthread_mutex_lock` / `_unlock` — channel π-calcolo.

#### `<stdarg.h>`
- `va_list` / `va_start` / `va_arg` / `va_end` — runtime variadic.

### Direttive sorgente

| Direttiva                                  | Effetto                                                |
| ------------------------------------------ | ------------------------------------------------------ |
| `// mnemo-main-argc: N`                    | `argc` iniziale (default 0)                            |
| `// mnemo-skip-par-shared-mutex-check`     | Disabilita check statico mutex condivisi tra par      |
| `// KAIROS_ALLOW_PAR_SHARED_INT`           | Permette int condiviso tra par branches                |

---

## Make targets

| Target                                  | Cosa fa                                                 |
| --------------------------------------- | ------------------------------------------------------- |
| `make venv`                             | Crea `.venv` + `pip install -e .`                       |
| `make compile`                          | Compila tutti gli esempi a `.kairos`                    |
| `make run FILE=c_test/loop.c`           | End-to-end single file                                  |
| `make test-unit`                        | Unit Python (no VM)                                     |
| `make test`                             | Compile + run di ogni esempio (timeout 5s)              |
| `make test-gcc-compat`                  | Diff comportamentale gcc-vs-Mnemo                       |
| `make test-gcc-compat-stop`             | Fail-fast version                                       |
| `make clean-kairos`                     | Rimuove `.kairos` generati                              |

`make test-gcc-compat COMPAT_ARGS='--category control'` per filtrare.

---

## Esclusioni note

Vedi `TODO.md` per dettagli. Esclusi strutturalmente:

- Floating-point (`float`/`double`/`<math.h>`).
- I/O reale (`scanf`, `fopen`, `fread`, ...).
- `goto`, `setjmp`/`longjmp`, `_Atomic`, inline asm.
- Multi-TU / linker.
- `__attribute__`, `__builtin_*`.
- VLA (array runtime-sized).
- `signal`/handlers, `exit`/`abort` dentro funzioni.
- `errno`, `argv` POSIX reali (solo stub).

---

## Licenza

Vedi `LICENSE` nel repo.
