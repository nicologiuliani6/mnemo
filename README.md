# Mnemo

**Mnemo** è una toolchain che compila un **subset reversibile di C** in programmi **Kairos** (`.kairos`), eseguibili sulla **VM reversibile** del repository **[Kairos](https://github.com/nicologiuliani6/kairos)** (clone separato accanto a questo repo, oppure path impostato con `KAIROS_ROOT`). Non è un compilatore C generico: è un ponte tra un linguaggio familiare (C ristretto) e un modello di calcolo dove ogni passo può essere invertito — variabili intere, stack di storia, `if`/`fi`, `from`/`until`, `par`/`rap`, canali e vincoli descritti nel README Kairos.

---

## Indice

1. [Struttura del progetto](#struttura-del-progetto)
2. [Installazione e compilazione](#installazione-e-compilazione)
   - [Requisiti](#requisiti)
   - [Setup da zero](#setup-da-zero)
   - [Posizione del repository Kairos](#posizione-del-repository-kairos)
3. [Toolchain — Makefile e CLI](#toolchain--makefile-e-cli)
4. [Architettura interna](#architettura-interna)
5. [Relazione con Kairos (runner, VM, uscita)](#relazione-con-kairos-runner-vm-uscita)
6. [Librerie `lib/*.kairos` e inclusione automatica](#librerie-libkairos-e-inclusione-automatica)
7. [Memoria unificata, pool e limiti](#memoria-unificata-pool-e-limiti)
8. [Parallelismo e ABI pthread](#parallelismo-e-abi-pthread)
9. [Esempi di header: `mps.h`, `mnemo_sync_print.h`](#esempi-di-header-mpsh-mnemo_sync_printh)
10. [Direttive nel sorgente C](#direttive-nel-sorgente-c)
11. [Mnemo rispetto al C standard](#mnemo-rispetto-al-c-standard)
12. [Subset C — dettaglio](#subset-c--dettaglio)
13. [Formato IR](#formato-ir)
14. [Test](#test)
15. [Errori comuni](#errori-comuni)
16. [Licenza e progetto](#licenza-e-progetto)

---

## Struttura del progetto

```
mnemo/
├── Makefile
├── README.md
├── pyproject.toml
├── mps.h                      ← API producer/consumer sincrona (POSIX + ramo MNEMO per VM)
├── mnemo_sync_print.h         ← printf serializzato tra thread (opzionale)
├── PC.c                       ← esempio dimostrativo parallelo
├── mnemo/
│   ├── __init__.py
│   ├── __main__.py            ← entry point pacchetto
│   ├── cli.py                 ← comandi compile / run / dump-ir
│   ├── compile.py             ← orchestrazione parse → layout → lower → emit
│   ├── c_parse.py             ← preprocess (gcc -E) + pycparser
│   ├── c_lower.py             ← AST C → IR (Program, Function, …)
│   ├── layout_collect.py      ← celle __mn_mem*, partizioni PAR, slot condivisi
│   ├── emit_kairos.py         ← IR → testo Kairos
│   ├── ir.py                  ← definizione istruzioni IR
│   ├── prelude.py             ← preambolo e fusione librerie
│   ├── ptr_pool_kairos.py     ← generazione procedure __mn_pool_* (N celle)
│   ├── inline_user.py         ← inline funzioni utente se serve rispettare limiti call
│   ├── par_shared_mutex_check.py
│   ├── kairos_limits.py       ← tetto argomenti/parametri VM
│   ├── errors.py
│   └── ir_dump.py
├── lib/
│   ├── helpers.kairos
│   ├── mul.kairos
│   ├── divmod.kairos
│   ├── mod.kairos
│   ├── bits.kairos
│   ├── putd.kairos            ← stampa decimale per printf %d non costante
│   └── ptr_pool.kairos        ← stub; __mn_pool_* generate a compile-time
├── c_examples/
│   └── ex00_*.c … ex35_*.c    ← esempi per make test
├── tests/
│   ├── test_parallel_partition.py
│   └── test_par_shared_mutex.py
└── runtime/
    └── README.md
```

Il repository **Kairos** (VM, frontend `src/kairos.py`, `build/libvm.so`) va tenuto separato; Mnemo non lo vendorizza.

---

## Installazione e compilazione

### Requisiti

| Componente | Note |
|------------|------|
| Python | ≥ 3.10 |
| gcc | Nel `PATH`; usato come preprocessore (`gcc -E`) per pycparser |
| pycparser | Dipendenza del pacchetto (`pip install -e .`) |
| Repo Kairos | Per `mnemo run` / `make test`: venv, `make build-release` → `build/libvm.so` |

### Setup da zero

```bash
# 1. Clone Mnemo (e accanto, clone Kairos — vedi sotto)
git clone <URL-del-repo-mnemo>
cd mnemo

# 2. Virtualenv e installazione editabile
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Nel repo Kairos: compila la VM
cd ../kairos
make install-deps    # se usi il makefile Kairos
make build-release

# 4. Torna in Mnemo e prova
cd ../mnemo
mnemo compile c_examples/ex00_add_simple.c   # eseguibile + libvm.so (serve gcc)
mnemo dump-kairos c_examples/ex00_add_simple.c   # solo .kairos
mnemo run c_examples/ex00_add_simple.c
```

### Posizione del repository Kairos

Layout consigliato (stessa directory padre):

```text
.../mnemo/
.../kairos/          ← venv, build/libvm.so
```

Se Kairos non è in `../kairos`:

```bash
export KAIROS_ROOT=/percorso/al/repo/kairos
# oppure
export MNEMO_KAIROS_ROOT=/percorso/al/repo/kairos
```

Il **Makefile** di Mnemo usa `KAIROS_ROOT` con default `$(pwd)/../kairos`.

---

## Toolchain — Makefile e CLI

### Makefile (root Mnemo)

| Comando | Descrizione |
|---------|-------------|
| `make` / `make help` | Riepilogo target |
| `make venv` | Crea `.venv` ed esegue `pip install -e .` |
| `make compile` | `mnemo dump-kairos` su tutti `c_examples/*.c` → `.kairos` |
| `make test-unit` | `pytest` / unittest in `tests/` **senza** eseguire la VM |
| `make test` | Compila esempi, richiede Kairos in `KAIROS_ROOT`, `make build-release`, esegue ogni `.kairos` con timeout |
| `make test-gcc-compat` | Confronta `mnemo run` vs `gcc` su `c_examples/gcc_compat/generic_*.c` (stdout + exit code + warning gcc = fail) |
| `make test-gcc-compat-stop` | Come sopra, ma si ferma al primo failure |
| `make run FILE=c_examples/ex00_add_simple.c` | Compila ed esegue un singolo `.c` |
| `make run FILE=… MAIN_ARGC=N` | Equivale a `--main-argc N` (senza spazi strani dopo `FILE=`) |
| `make clean-kairos` | Rimuove `c_examples/*.kairos` generati |

Note rapide per `test-gcc-compat`:

- puoi passare argomenti al runner con `COMPAT_ARGS`, es.:
  - `make test-gcc-compat COMPAT_ARGS='--stop-on-first-fail'`
  - `make test-gcc-compat COMPAT_ARGS='--category control'`
- categorie macro disponibili: `types`, `expr`, `control`, `ptr`, `struct_union`, `runtime`
- artifact dei mismatch: `c_examples/gcc_compat/artifacts/*.json`

### CLI `mnemo`

```bash
mnemo compile sorgente.c                    # → eseguibile nativo (stem) + libvm.so (stessa dir); niente dump VM
mnemo compile sorgente.c -o mioapp         # nome eseguibile; copia libvm.so accanto
mnemo compile sorgente.c --keep-kairos      # emette anche sorgente.kairos per ispezione
mnemo dump-kairos sorgente.c                # solo testo .kairos accanto al .c
mnemo dump-kairos sorgente.c -o out.kairos
mnemo dump-kairos sorgente.c --stdout
mnemo compile sorgente.c -v                 # stampa comando gcc e path
mnemo compile sorgente.c --main-argc N
mnemo compile sorgente.c --ptr-pool-size N  # default 4; tetto in kairos_limits.py

mnemo run sorgente.c
mnemo run sorgente.c --main-argc N --ptr-pool-size N -v
mnemo run sorgente.c --kairosapp /percorso/kairosapp

mnemo dump-ir
mnemo emit-kairos
```

Variabili d’ambiente:

| Variabile | Uso |
|-----------|-----|
| `KAIROS_ROOT`, `MNEMO_KAIROS_ROOT` | Root del repo Kairos per il runner |
| `MNEMO_KAIROSAPP` | Eseguibile alternativo a `python -m src.kairos` |

Se modifichi i sorgenti C della VM Kairos, esegui di nuovo `make build-release` nel repo Kairos prima di `mnemo run`, altrimenti resta in uso un `libvm.so` obsoleto (il frontend Kairos segnala avvisi simili su *stderr*).

---

## Architettura interna

```text
file.c
    │
    ▼
[ gcc -E -DMNEMO ]  ──  preprocessore (no stdio completo nel parse)
    │
    ▼
[ pycparser ]  ──  AST C (`c_ast`)
    │
    ▼
[ layout_collect.py ]  ──  ProgramMemLayout: slot __mn_mem*, partizione 2·S per PAR, slot condivisi
    │
    ▼
[ c_lower.py ]  ──  AST → IR (`Program`, `Function`, ICall, IPar, ISsend, …)
    │
    ▼  (opzionale)
[ inline_user.py ]  ──  se troppe celle / troppi argomenti per le `call` Kairos
    │
    ▼
[ prelude.py + lib/*.kairos + ptr_pool_kairos(N) ]  ──  preambolo unico
    │
    ▼
[ emit_kairos.py ]  ──  testo sorgente `.kairos`
    │
    ▼
[ python -m src.kairos ]  ──  frontend Kairos → bytecode → libvm.so
```

L’**IR** è definito in `mnemo/ir.py` (costanti, `+=`/`-=`, `IHistPush`, `IIfKairos`, `IFromUntilKairos`, `ILocalBlock`, `IPar`, canali, ecc.).

---

## Relazione con Kairos (runner, VM, uscita)

- Il bytecode viene prodotto dal **frontend Python di Kairos** e passato a **`libvm.so`** (`vm_run_from_string`).
- **`mnemo run`** risolve il runner in ordine:
  1. `venv/bin/python -m src.kairos` sotto `KAIROS_ROOT` / `MNEMO_KAIROS_ROOT` / `../kairos`;
  2. oppure `kairosapp` o `MNEMO_KAIROSAPP` / `--kairosapp`.
- Il runner stampa anche il **dump VM** (`=== VM dump ===`). Il valore di ritorno di `main` è emesso come `show` su `__mn_exit`; **`mnemo run`** tenta di usare `__mn_exit: N` come **codice di uscita** del processo se la VM termina con successo.

Programmi con **`par`** e variabili `int` condivise tra rami possono richiedere (Mnemo la inserisce quando serve):

```text
// KAIROS_ALLOW_PAR_SHARED_INT
```

Per il **linguaggio Kairos** (reversibilità, `push`/`pop`, `if`/`fi`, canali, `par`, controlli statici) fare riferimento al **README del repository Kairos** (nel clone locale, di solito nella directory accanto a Mnemo) o alla documentazione installata con il pacchetto Kairos.

---

## Librerie `lib/*.kairos` e inclusione automatica

Mnemo **non** richiede `#include` verso i `.kairos`: le procedure vengono aggiunte automaticamente.

1. **Operatori:** compaiono `*`, `/`, `%` → `mul.kairos`, `divmod.kairos` / `mod.kairos`, `helpers.kairos`; per bitwise → `bits.kairos` (che dipende da mul/divmod/helpers).
2. **`printf`** con `%d` e argomenti non costanti → anche `putd.kairos` (e dipendenze già citate).
3. **Chiamate:** `f(...)` definita nel `.c` → lowering coerente; `f` solo dichiarata e non built-in → ricerca `procedure f(` in `lib/*.kairos`.
4. **`malloc` / `free`** → pool (`ptr_pool.kairos` + emissione `emit_ptr_pool_kairos` con `N` dal layout).

Se due file in `lib/` definiscono la stessa `procedure`, la compilazione fallisce con errore esplicito.

| File | Ruolo tipico |
|------|----------------|
| `helpers.kairos` | Movimenti e helper reversibili base. |
| `mul.kairos` | `__mn_mul_into`. |
| `divmod.kairos` | `__mn_divmod_nonneg`. |
| `mod.kairos` | `__mn_mod_nonneg`. |
| `bits.kairos` | AND/OR, shift via aritmetica. |
| `putd.kairos` | `__mn_putd` / `__mn_putd_uint` per `%d` dinamico. |
| `ptr_pool.kairos` | Riferimento; le `__mn_pool_*` sono generate con `N` celle. |

---

## Memoria unificata, pool e limiti

- Le celle del programma sono **`__mn_mem0` … `__mn_mem{N-1}`** con `N` derivato dal **layout** (variabili, `malloc`, partizione parallela, ecc.).
- **`--ptr-pool-size`** influenza il layout quando applicabile (default **4** nel CLI). Esiste un tetto **`PTR_POOL_MAX`** in `mnemo/kairos_limits.py`.
- La VM Kairos ha limiti su **numero di argomenti per `call`** e **parametri per procedura** (ordine di grandezza documentato in `kairos_limits.py`). Oltre quella soglia Mnemo usa pool **bancati** (`__mn_pool_store_b0`, …) e, per funzioni utente nello stesso file se necessario, **`inline_user`** — l’inline **non** è compatibile con l’ABI `mnemo_pthread_parallel2` a due worker sullo stesso file se servono entrambe le cose: vedi messaggi di compilazione.

---

## Parallelismo e ABI pthread

Mnemo abbassa questi costrutti a **`par … and … rap`** (due thread Kairos):

| ABI | Uso |
|-----|-----|
| `mnemo_pthread_parallel2(a, b)` | Due worker `void (*)(void)` (firma generica in VM). |
| `mnemo_pthread_parallel2(a, b, …)` | Argomenti nell’ordine della firma C: prima tutti i parametri di `a`, poi di `b`. |
| `mnemo_pthread_parallel_with(w, c)` | Worker + continuazione. |
| `mnemo_pthread_parallel_with1(w, arg, c)` | Worker con un argomento scalare. |
| `mnemo_pthread_start` / `mnemo_pthread_start1` | Un solo ramo par/rap. |

**Due finestre di memoria:** il ramo sinistro usa `__mn_mem0…S-1`, il destro `__mn_memS…2S-1`; gli indici in `parallel_file_shared_slots` usano lo **stesso** actual `__mn_mem{i}` in entrambi i rami (es. un campo struct condiviso).

**`pthread_mutex_t`** nel modello Mnemo diventa **canale** Kairos (token stile π-calcolo). Per controlli statici aggiuntivi: `mnemo/par_shared_mutex_check.py` e `// mnemo-skip-par-shared-mutex-check` (commento nelle prime righe del `.c`).

**`mps.h`:** in **POSIX** la sincronizzazione producer/consumer usa due semafori (`g_slot_free`, `g_data_ready`) per un buffer implicito da un elemento. Nel ramo **`#ifdef MNEMO`** la stessa logica è replicata con **due** mutex-canale (non basta un solo `g_xfer`: con `par` reale i token possono accumularsi e i valori letti saltano). In `destroy_mutexes` (MNEMO) è necessario un `pthread_mutex_unlock` su `g_data_ready` prima dei `destroy`, perché il lowering di `pthread_mutex_destroy` esegue un `srecv` che si aspetta un token residuo.

---

## Esempi di header: `mps.h`, `mnemo_sync_print.h`

- **`mps.h`**: struct `mps_t`, `init_mutexes` / `destroy_mutexes`, `ssend` / `srecv`, e sotto `#ifndef MNEMO` il wrapper `mnemo_pthread_parallel2` per **gcc** + pthread reale.
- **`mnemo_sync_print.h`**: mutex globale dedicato alla stampa; dopo l’include, **`printf`** è ridefinito come stampa serializzata (`(printf)(…)` evita ricorsione di macro). Richiede `MNEMO_SYNC_PRINT_DEFINE_MUTEX` in **una** unità di traduzione, più `mnemo_sync_print_setup` / `teardown` attorno ai thread. Con **`-DMNEMO`** non si include `<stdio.h>` (evita `stdarg.h` nel parse).

---

## Direttive nel sorgente C

| Direttiva | Effetto |
|-----------|---------|
| `// mnemo-main-argc: N` | Valore iniziale di `argc` per `int main(int argc, …)` (≥ 0). Default **0** se assente. Sovrascrivibile con `--main-argc` / `MAIN_ARGC=`. |
| `// mnemo-skip-par-shared-mutex-check` | Disattiva il controllo statico su slot condivisi + mutex nel PAR (casi avanzati). |

---

## Mnemo rispetto al C standard

Mnemo **non** implementa il C di ISO/IEC: il preprocessore è quello di **gcc -E**, ma l’AST viene interpretato da un **subset** pensato per abbassare a **Kairos**. Qui: cosa puoi ragionevolmente aspettarti come in C, e cosa **manca** o **è diverso**.

### C’è (in sintesi, come nel C “di tutti i giorni”)

| Area | Cosa è previsto |
|------|------------------|
| **Struttura del programma** | Funzioni, parametri, variabili locali/globali/file-scope, blocchi `{ }`, visibilità di base. |
| **Tipi scalari** | `int`, `unsigned` / `unsigned int`, `_Bool` / `bool`, `char` (incl. letterali carattere dove supportato). |
| **Tipi derivati** | `typedef`, `struct` (campi scalari e sotto-struct anonime), `union` (solo membri scalari), `enum`. |
| **Puntatori** | `int *`, `void *`, ecc.; dereferenziazione `*p`, assegnamento `*p = …`; subset di `malloc` / `free` sul **pool** Mnemo. |
| **Array** | Array statici e multidimensionali row-major; array parametro con decay a puntatore; inizializzatori in molti casi. |
| **Operatori** | `+ - * / %`, unario `-`, confronti, AND/OR/NOT logici, `sizeof`, cast verso tipi supportati, `?:`, virgola `,`, `^` / `^=`. |
| **Assegnamenti** | `=`, `+=`, `-=`, …, `++` / `--` come **istruzione** su `int`. |
| **Controllo** | `if` / `else`, `while`, `do` / `while`, `for`, `break`, `continue`; `switch` / `case` / `default` con `break` obbligatorio a fine ramo. |
| **Funzioni** | `void`, `int`, tipi scalari come sopra; chiamate e ricorsione (nei limiti di layout/VM); `main` come in C (con `argc` / `argv` **limitati**, vedi sotto). |
| **I/O minimo** | `putchar`, `printf` con **sottoinsieme** di formati (es. `%d`, `%c`, `%s` in scenari supportati); niente libc completa. |
| **Concorrenza (astratta)** | ABI stile `pthread` / `mnemo_pthread_*` abbassate a `par` Kairos; mutex come **canali** nella VM. |

### Non c’è (o non è il C “vero”)

| Cosa manca o è diverso | Nota |
|-------------------------|------|
| **C standard completo** | Nessuna garanzia di conformità ISO; molte regole e UB del C pieno **non** si applicano: vale il modello Kairos / IR. |
| **Virgola mobile** | Nessun `float` / `double`. |
| **VLA** | Array a lunghezza variabile (`int a[n]` con `n` runtime) non supportati. |
| **Variadiche C** | Niente `f(...)` con `va_list` / `stdarg`; le variadiche sono solo lato **preprocessore** (es. macro `printf` in header che espandono prima del parse Mnemo). |
| **`goto`**, **`setjmp`**, inline assembly | Non supportati. |
| **Bit-field** | Non supportati. |
| **`&` (indirizzo) generico** | Solo nel **subset** documentato (es. `&x`, `&struct.campo` dove il lowering lo ammette); non tutti gli indirizzi del C. |
| **Aritmetica puntatori** | Non la stessa libertà del C: niente “cursori” arbitrari su `p+1` in generale. |
| **Libreria C standard** | Non c’è `stdio` / `string` / `stdlib` **POSIX** nel senso di linking: ciò che usi deve essere **built-in** Mnemo (`printf` limitato, `malloc`/`free` pool) o **tuo** codice / header minimi. |
| **`#include`** | Il preprocessore gira, ma includere header pesanti (es. `<stdio.h>` con `-DMNEMO`) può **rompere il parse** (`stdarg.h`, ecc.). |
| **`argv` / ambiente OS** | `argv` è uno **stub** sintattico; non è un array di stringhe reali come su POSIX. |
| **`main` e uscita** | Il valore di ritorno è propagato come `__mn_exit` nella VM, non sempre identico a `exit()` POSIX. |
| **Thread** | Con **`mnemo run`** i “pthread” sono **thread Kairos** (`par`), non pthread del kernel; con **gcc** su `mps.h` senza `MNEMO` sono pthread reali **solo** dove l’header lo definisce. |
| **Memoria** | Heap = **pool** a indici; puntatori sono **indici** nel modello, non indirizzi macchina. |
| **Passaggio struct/union per valore** | Non nel subset attuale (oltre i casi esplicitamente supportati dal compilatore). |

Per il dettaglio sintattico e i limiti pratici vedi la sezione seguente e i messaggi del compilatore (`mnemo compile`).

---

## Subset C — dettaglio

### Tipi e funzioni

| Elemento | Supporto |
|----------|----------|
| `main` | `int main(void)` o `int main(int argc, char **argv)` |
| Altri ritorni | `void`, `int`, `unsigned`, `_Bool`/`bool`, puntatori scalari |
| Tipi compositi | `typedef`, `struct`, `union`, `enum` |
| Parametri | Scalari; array parametro `int a[N]` → decay a puntatore |
| Struct / union | Campi scalari, annidamento, `sizeof`; union solo scalari |
| Ritorno `int` | Convenzione Kairos: ultimo parametro `int __mn_ret` nella procedura emessa |

### Puntatori, `malloc`, `sizeof`

- Puntatori nel subset sono **indici** nel pool; `*p` e assegnamento supportati; aritmetica puntatori limitata.
- **`malloc`/`free`** con `sizeof` costante a compile-time; modello dimensioni stile LP32-like nel lowering (scalari/puntatori 4 byte, `char` 1).
- **`argv`**: stub sintattico, non è un vero array di stringhe POSIX.

### Espressioni e controllo

- Aritmetica `+ - * / %`, unario `-`, `sizeof`, cast, `?:`, `,`, `^` / `^=`.
- Assegnamenti `=`, `+=`, …, `++`/`--` come istruzione su `int`.
- `if`/`else`, `while`, `do`/`while`, `for`, `break`, `continue`.
- `switch`/`case`/`default` con `break` obbligatorio a fine ramo.

### Non supportato (estratti)

Vedi anche [Mnemo rispetto al C standard](#mnemo-rispetto-al-c-standard).

- VLA, **funzioni variadiche C**, `goto`, floating point, bit-field, `&` oltre il modello pool, molte estensioni GCC.
- `stdio.h` nel preprocessato Mnemo: tipicamente **evitato** dove introduce `stdarg.h` non parsabile.
- Passaggio/ritorno struct o union per valore oltre il subset; semantica UB del C pieno — valgono i vincoli delle procedure Kairos (es. divisori positivi dove richiesto).

---

## Formato IR

Definito in **`mnemo/ir.py`**: costanti, add/sub/xor in-place, swap, storia (`IHistPush`, `IStoreRev`), chiamate, costrutti Kairos (`IIfKairos`, `IFromUntilKairos`, `ILocalBlock`, `IPar`), canali (`ISsend`/`ISrecv`), ecc.

---

## Test

```bash
make test-unit    # rapido, senza VM
make test         # richiede Kairos in KAIROS_ROOT, build-release, timeout sugli esempi
```

I sorgenti di esempio sono in **`c_examples/`** (`ex00` … `ex35`). In root possono esserci anche `PC.c`, `test.c` dimostrativi.

---

## Errori comuni

### Runner Kairos non trovato

Impostare `KAIROS_ROOT` o `MNEMO_KAIROS_ROOT`, oppure usare `--kairosapp`. Verificare `venv` e `python -m src.kairos` nel repo Kairos.

### `cannot open shared object file: libvm.so` / VM obsoleta

Nel repo Kairos: `make build-release`. Eseguire di nuovo `mnemo run` dopo aver ricompilato la VM.

### Errori VM su `LOCAL` / `DELOCAL` / ordine `delocal`

Il Kairos emesso deve bilanciare `local`/`delocal` su ogni percorso; le librerie in `lib/` e il lowering in `c_lower.py` devono rispettare la VM in uso.

### `Troppi argomenti in call`

Ridurre celle di layout, `--ptr-pool-size`, spezzare il programma; verificare se l’inline può applicarsi (non compatibile con alcuni schemi pthread sullo stesso file).

### `[STATIC]` / race PAR / mutex (Mnemo)

Seguire i messaggi di `par_shared_mutex_check.py`; usare canali coerenti per handshake; per producer/consumer a buffer 1 elemento usare due semafori (POSIX) o due canali (MNEMO), come in `mps.h`.

### `printf %d` solo costanti

Servono argomenti interi non costanti supportati tramite `putd.kairos` e inclusione automatica quando il sorgente usa `printf`.

---

## Licenza e progetto

Versione pacchetto: vedi **`pyproject.toml`**. Per contribuire, mantenere allineamento con le convenzioni del codice esistente (`mnemo/c_lower.py`, `emit_kairos.py`, ecc.) e con i vincoli della **VM Kairos** in uso.
