# Mnemo

Mnemo compila un **sottoinsieme di C** in [Kairos](https://github.com/nicologiuliani6/kairos), un linguaggio reversibile e concorrente. Il programma C diventa un programma Kairos che si può eseguire in avanti e **all'indietro**: ogni assegnamento distruttivo salva il valore perso su uno stack di storia, così l'intera esecuzione resta invertibile.

Mnemo genera solo Kairos puro (nessuna estensione della VM) e mira a produrre lo stesso output e lo stesso exit code di `gcc` sui programmi del sottoinsieme.

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
mnemo run esempio.c          # 30
```

---

## Indice

1. [Installazione](#installazione)
2. [Uso](#uso)
3. [Come funziona](#come-funziona)
4. [Il sottoinsieme di C](#il-sottoinsieme-di-c)
5. [Parallelismo e canali](#parallelismo-e-canali)
6. [try / rollback](#try--rollback)
7. [Verifica e test](#verifica-e-test)
8. [Differenze note rispetto a gcc](#differenze-note-rispetto-a-gcc)

---

## Installazione

Mnemo non include Kairos: il repository Kairos va clonato accanto (default `../kairos`, oppure `KAIROS_ROOT=/percorso`) e compilato.

```bash
git clone https://github.com/nicologiuliani6/kairos.git
git clone https://github.com/nicologiuliani6/mnemo.git
(cd kairos && make install-deps && make)
cd mnemo && make venv          # .venv + pip install -e .
```

Requisiti: Python ≥ 3.10, `gcc` (anche come preprocessore), `make`.

| Variabile | Default | Effetto |
|---|---|---|
| `KAIROS_ROOT` / `MNEMO_KAIROS_ROOT` | `../kairos` | repository Kairos usato per eseguire |
| `MNEMO_KAIROSAPP` | `kairosapp` | eseguibile alternativo per `mnemo run` |

---

## Uso

```bash
mnemo run prog.c [opzioni]                     # compila in .kairos ed esegue
mnemo dump-kairos prog.c [-o out.kairos] [--stdout]
mnemo compile prog.c [-o exe] [--keep-kairos]   # eseguibile nativo: bytecode + libvm.so, senza Python
```

`mnemo run` stampa l'output del programma ed esce con il valore restituito da `main`.

| Opzione | Effetto |
|---|---|
| `--main-argc N` | valore di `argc` (altrimenti la direttiva `// mnemo-main-argc: N`, altrimenti 0) |
| `--ptr-pool-size N` | celle di heap ad accesso diretto, prima del nastro (vedi [Memoria](#memoria)) |
| `--arr-max N` | limite di elementi per array (di default dedotto dal sorgente, minimo 1024) |
| `--opt-uncall-user-calls` | dopo ogni chiamata idonea ne libera la storia (vedi sotto) |
| `--check-invertibility` | esegue `main` e poi lo inverte: la VM segnala ogni passo non invertibile |
| `--auto` (solo `run`) | decide da solo se attivare `--opt-uncall-user-calls` |
| `--vm-dump`, `--vm-stats` (solo `run`) | stampa il dump finale della VM / quante celle restano vive |
| `-v` | comandi e codici di uscita su stderr |

---

## Come funziona

```
prog.c ─ gcc -E -DMNEMO ─ pycparser ─▶ AST
      ─ trasformazioni (return anticipati, switch, static, stdlib…)
      ─ layout_collect.py   una cella di memoria per ogni variabile, array, campo
      ─ c_lower.py          AST → IR (assegnamenti reversibili, storia, if/from)
      ─ arrayize.py         celle → array Kairos __mn_mem
      ─ prelude.py + lib/   procedure di libreria (stampa, bit, divisione…)
      ─ emit_kairos.py      IR → testo .kairos ─▶ VM Kairos
```

### Reversibilità

C distrugge informazione (`x = 5` perde il vecchio `x`); Kairos no. Mnemo scrive ogni assegnamento come `push(x, __mn_hist); x += 5`: il vecchio valore va sullo stack di storia `__mn_hist`, i temporanei su `__mn_scratch`. L'esecuzione all'indietro li ripesca. Le strutture di controllo diventano `if … fi` e `from … until` di Kairos con le guardie d'uscita necessarie all'inversione.

### Memoria

Tutto lo stato con nome del programma (scalari, array, struct, globali) e la prima parte dell'heap di `malloc` stanno in un unico array Kairos `int __mn_mem[N]`; un puntatore è un indice. Le procedure ricevono l'array per riferimento; `a[i]` con indice calcolato a runtime diventa un accesso diretto `__mn_mem[(base + i)]`, `*p` un accesso diretto all'array o al nastro.

L'heap non ha limite. La sua prima parte sta in coda all'array (dimensione dedotta dalle `malloc` del sorgente, almeno 1024 celle se il programma ne usa; `--ptr-pool-size N` la alza). Gli array Kairos non crescono, quindi oltre la fine dell'array l'heap prosegue su un **nastro** di due stack Kairos con un cursore in mezzo: lì un accesso costa la distanza dall'accesso precedente (scorrere un blocco è O(1) per cella, i salti lunghi costano di più) e il nastro si allunga da solo. `free` riusa solo l'ultimo blocco allocato.

### `--opt-uncall-user-calls`

La storia cresce a ogni assegnamento. Con questa opzione, dopo `call f(…)` Mnemo salva le celle scritte da `f`, fa `uncall f` (che svuota la storia prodotta da `f`) e rimette i risultati con uno scambio XOR: stesso risultato, molta meno memoria su programmi lunghi. Restano escluse la ricorsione diretta, le funzioni con canali o `par`, e le funzioni che scrivono attraverso parametri puntatore fuori dai cicli.

### Librerie Kairos (`lib/`)

Incluse automaticamente quando servono: `putd`/`putx`/`puto` (stampa di interi in base 10/16/8, con larghezza e padding), `bits` (`&`, `|`, `<<`, `>>`), `divmod`, `mul`, `mod`, `helpers` (maschera a 32 bit degli `unsigned`). `* / %` sono operatori nativi di Kairos.

---

## Il sottoinsieme di C

**Tipi.** `int`, `unsigned`, `char` (anche aritmetica a 8 bit), `bool`/`_Bool`, `short`/`long`/`long long` (come `int`), `size_t`, `int*_t`/`uint*_t`, `enum`, `struct`, `union` (anche annidate), `typedef`. Niente floating point.

**Puntatori.** `void *`, puntatori multipli (`int **`), aritmetica (`p + i`, `p++`, `q - p`), `&x`, `&s.campo`, `&a[i]`, puntatori a struct e a righe di matrici (`int (*r)[N]`), `malloc`/`calloc`/`free`.

**Array.** Multidimensionali, inizializzatori (anche designati), indice calcolato a runtime, passaggio a funzione come puntatore. Niente VLA.

**Controllo.** `if`, `switch` (corpo tra `{}`), `while`, `do`, `for`, `break`, `continue`, `return` ovunque, operatore ternario, `&&`/`||` con cortocircuito, `_Generic`. Niente `goto`, `setjmp`, `_Atomic`, asm, bit-field.

**Funzioni.** Ricorsione anche mutua, `struct` per valore e come ritorno, puntatori a funzione (assegnati, in array a indice runtime, come parametro, come campo di struct, restituiti da funzione). `main` è `void`, `int argc` o `int argc, char **argv` (`argv` è solo sintattico). Niente funzioni variadiche definite dall'utente.

**Stringhe.** `char *` da letterali (anche riassegnati e restituiti), `char s[] = "…"`, `printf("%s", …)`.

**Libreria standard** (molte funzioni sono valutate in compilazione su argomenti costanti):

| Header | Supporto |
|---|---|
| `stdio.h` | `printf` (`%d %i %u %x %X %o %c %s %p %%`, larghezza, `-`, `0`, `l`/`ll`), `putchar`, `puts`, `sprintf`/`snprintf` su argomenti costanti; `fprintf`/`fputs`/`fputc` su `stdout` (su `stderr` sono muti); `fflush` & co. valgono 0 |
| `stdlib.h` | `malloc`, `calloc`, `free`, `abs`/`labs`/`llabs`, `div`/`ldiv`, `atoi`/`strtol`/`strtoul` su letterali, `exit`/`abort` solo in `main`, `getenv` → `NULL` |
| `string.h` | `strlen`, `strcmp`, `strncmp`, `strchr`, `strrchr`, `strstr`, `strspn`, `memcmp`, `memchr`, `strcpy`, `strcat`, `memcpy`, `memset`, `memmove`, `strdup`, `strerror` |
| `strings.h` | `bzero`, `bcopy`, `index`, `rindex`, `strcasecmp` |
| `stdarg.h` | `va_list`, `va_start`, `va_arg`, `va_end` |
| `time.h`, `locale.h` | `time`/`clock` → 0, `setlocale` → `NULL` |

Direttive nel sorgente: `// mnemo-main-argc: N`.

---

## Parallelismo e canali

```c
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));
```

Con due funzioni distinte diventa un `par … and … rap` di Kairos: due thread reali. In Kairos i rami di un `par` non condividono memoria scrivibile, quindi il ramo destro lavora su una propria finestra di memoria (`__mn_memR`, con una copia delle globali che legge). Una variabile globale **scritta** da un ramo e usata dall'altro è un errore di compilazione: i rami comunicano solo con i canali. `parallel2(f, f)` con la stessa funzione è eseguito in sequenza. Varianti: `mnemo_pthread_parallel_with(worker, cont)` e `mnemo_pthread_parallel_with1(worker, arg, cont)`.

I canali sono quelli sincroni di Kairos:

- `mnemo_kairos_channel_t` con `ssend`/`srecv`, anche con passaggio di canali (vedi `tests/c/examples_advanced/pi_calculus.c` e `mnemo_kairos_pi.h`);
- il modello produttore/consumatore di `tests/c/examples_advanced/mps.h`, dove un campo `pthread_mutex_t lane` funge da canale.

`pthread_mutex_lock`/`unlock` su un mutex vero sono **no-op**: non essendoci memoria condivisa fra i rami non c'è nulla da proteggere, e un canale rendez-vous non può fare da mutex simmetrico. Conseguenza: le `printf` di due rami paralleli possono mescolarsi carattere per carattere.

---

## try / rollback

Estensione di Mnemo che si appoggia al `try` di Kairos:

```c
try (x < 10) {
    x += passo;          /* eseguito in avanti */
} rollback {
    tentativi++;         /* se la condizione è falsa: corpo annullato, poi questo */
}
```

La condizione, valutata dopo il corpo, è un confronto semplice; niente `par` o canali nel corpo. Esempi: `tests/c/repro/try_*.c`, `tests/c/examples_advanced/maze_backtrack.c`.

---

## Verifica e test

| Comando | Cosa fa |
|---|---|
| `make test-unit` | test Python (`tests/test_*.py`) |
| `make test` | compila ed esegue `tests/c/examples/*.c` |
| `make test-gcc-compat` | 189 programmi: stdout ed exit code devono coincidere con `gcc` (`COMPAT_ARGS='--category control'` per filtrare, `…-stop` per fermarsi al primo errore) |
| `bash tests/c/probe/run.sh` | corpus più ampio di confronto 1:1 con `gcc` |
| `make run FILE=prog.c` | un singolo file |
| `make clean-kairos` | rimuove i `.kairos` generati |

`tests/c/repro/` raccoglie i casi di regressione e alcuni progetti più grandi (`encrypt.c`, `des.c`, `projects/`), `tests/c/examples_advanced/` gli esempi concorrenti.

---

## Differenze note rispetto a gcc

- `int` è a 64 bit: l'overflow con segno (comportamento indefinito in C) non avvolge a 32 bit; `unsigned` invece avvolge correttamente modulo 2³².
- `sizeof` di un puntatore vale 4 (una cella).
- Gli argomenti di una chiamata sono valutati da sinistra a destra.
- Niente I/O reale (file, input), niente segnali né `errno`.
- Le `printf` di due rami `par` possono mescolarsi (vedi sopra).
