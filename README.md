# Mnemo

**Mnemo** è una toolchain che compila un **subset reversibile di C** in programmi **Kairos** (`.kairos`), eseguibili sulla **VM reversibile** del repository **Kairos** (clone separato accanto a questo repo, o path impostato con `KAIROS_ROOT`). Non è un compilatore C generico: è un ponte tra un linguaggio familiare (C ristretto) e un modello di calcolo dove ogni passo può essere invertito, con variabili intere, stack di storia e costrutti `if`/`fi`, `from`/`until`, `par`/`rap`.

---

## Cos’è e a cosa serve

- **Cosa fa:** traduce `file.c` → `file.kairos` unendo il `main` e le procedure di libreria necessarie, poi (opzionalmente) lancia la VM Kairos sul risultato.
- **Scopo:** scrivere algoritmi e test in uno stile vicino al C, mantenendo la **reversibilità** e i vincoli del linguaggio Kairos (nessuna moltiplicazione nativa, divisione solo tramite procedure dedicate, gestione esplicita di `local`/`delocal`, storia su stack, ecc.).
- **Per chi:** chi lavora su **computazione reversibile**, prototipi verso Kairos, o integrazioni con la VM senza scrivere a mano migliaia di righe di `.kairos`.

Flusso logico:

```text
file.c  →  preprocess (gcc -E) + pycparser  →  IR Mnemo  →  emit Kairos  →  file.kairos  →  VM Kairos
```

---

## Architettura della toolchain

| Fase | Modulo / artefatto | Ruolo |
|------|---------------------|--------|
| Parse C | `mnemo/c_parse.py`, **gcc** + **pycparser** | AST C dopo preprocessore. |
| Layout memoria | `mnemo/layout_collect.py` | Celle `__mn_mem*`, pool, eventuale partizione doppia per `par`. |
| Lowering | `mnemo/c_lower.py` | AST C → `Program` / `Function` / istruzioni IR. |
| Inline (opzionale) | `mnemo/inline_user.py` | Se il layout supera i limiti di argomenti delle `call` Kairos, le funzioni utente nello stesso file possono essere inlined in `main`. |
| Emissione | `mnemo/emit_kairos.py` | IR → testo Kairos (`procedure`, `local`/`delocal`, `push`/`pop`, …). |
| Preambolo | `mnemo/prelude.py`, `mnemo/lib/*.kairos`, `mnemo/ptr_pool_kairos.py` | Concatena le librerie richieste e genera le procedure `__mn_pool_*` dimensionate al layout. |
| CLI | `mnemo/cli.py` | `compile`, `run`, comandi di esempio IR. |

L’**IR** (tipi e istruzioni) è definito in `mnemo/ir.py`.

---

## Requisiti

- **Python** ≥ 3.10  
- **gcc** nel `PATH` (preprocessore per pycparser)  
- Dipendenze: **pycparser** (installate con il pacchetto)  
- Per eseguire sulla VM: clone del **repo Kairos** con `venv` e `build/libvm.so` (vedi sotto)

---

## Installazione

Layout consigliato (stessa directory padre):

```text
.../mnemo/     ← questo repository
.../kairos/    ← repository Kairos con venv e `make build-release`
```

```bash
cd mnemo
python3 -m venv .venv
source .venv/bin/activate   # oppure: .venv\Scripts\activate su Windows
pip install -e .
```

Se la VM non è in `../kairos`:

```bash
export KAIROS_ROOT=/percorso/al/repo/kairos
# oppure
export MNEMO_KAIROS_ROOT=/percorso/al/repo/kairos
```

Il **Makefile** usa `KAIROS_ROOT` con default `$(pwd)/../kairos`.

---

## Esecuzione: relazione con Kairos

- Il **bytecode** viene prodotto dal frontend Python di Kairos e passato a **`libvm.so`** (`vm_run_from_string`).
- **`mnemo run`** cerca in ordine:
  1. `venv/bin/python -m src.kairos` sotto `KAIROS_ROOT` / `MNEMO_KAIROS_ROOT` / `../kairos` rispetto al repo Mnemo;
  2. oppure l’eseguibile `kairosapp` o `MNEMO_KAIROSAPP` / `--kairosapp`.
- Il runner Python stampa anche il **dump VM** (`=== VM dump ===`). Il valore di uscita di `main` è emesso come `show(__mn_exit)` e **`mnemo run`** prova a usare `__mn_exit: N` come codice di uscita del processo (dopo aver verificato che la VM sia terminata con successo).

Programmi che usano **`par`** con variabili `int` condivise tra rami possono richiedere la prima riga:

```text
// KAIROS_ALLOW_PAR_SHARED_INT
```

Mnemo la inserisce automaticamente quando serve (memoria a due regioni + slot condivisi documentati).

---

## Interfaccia a riga di comando (`mnemo`)

```bash
# Compilazione
mnemo compile sorgente.c                    # → sorgente.kairos accanto al .c
mnemo compile sorgente.c -o out.kairos
mnemo compile sorgente.c --stdout         # Kairos su stdout
mnemo compile sorgente.c -v               # stampa il path del file scritto
mnemo compile sorgente.c --main-argc N    # argc per main(int argc, …)
mnemo compile sorgente.c --ptr-pool-size N  # influenza il layout heap/pool (default 4; tetto `PTR_POOL_MAX` in mnemo/kairos_limits.py)

# Compila ed esegue (preferisce python -m src.kairos del repo Kairos)
mnemo run sorgente.c
mnemo run sorgente.c --main-argc N
mnemo run sorgente.c --ptr-pool-size N
mnemo run sorgente.c -v
mnemo run sorgente.c --kairosapp /percorso/kairosapp

# Diagnostica IR (esempio minimale integrato)
mnemo dump-ir
mnemo emit-kairos
```

Variabili d’ambiente:

- **`KAIROS_ROOT`**, **`MNEMO_KAIROS_ROOT`**: root del repo Kairos per `mnemo run`.
- **`MNEMO_KAIROSAPP`**: eseguibile alternativo a `python -m src.kairos`.

---

## Makefile (root del repo Mnemo)

```bash
make help          # riepilogo
make venv          # crea .venv e pip install -e .
make compile       # mnemo compile su tutti c_examples/*.c
make test-unit     # unittest in tests/ (senza VM)
make test          # compile c_examples + build Kairos + esegue ogni .kairos (timeout 5s)
make run FILE=c_examples/ex00_add_simple.c
make run FILE=c_examples/ex21_loops_cond_main.c MAIN_ARGC=7   # come --main-argc 7
make clean-kairos  # rimuove c_examples/*.kairos
```

**Nota:** usare `MAIN_ARGC=N` senza spazi strani; `make run FILE=foo.c 7` è interpretato male da Make.

---

## Inclusione delle librerie `lib/*.kairos`

Mnemo **non** richiede `#include` verso Kairos: le procedure vengono aggiunte automaticamente.

1. **Operatori:** compaiono `*`, `/`, `%` → si tirano dentro `mul.kairos`, `divmod.kairos` / `mod.kairos`, `helpers.kairos`, e per operazioni bitwise **`bits.kairos`** (che a sua volta usa mul/divmod/helpers).
2. **Chiamate:** per ogni `f(...)` con `f` **definito** nel `.c` come funzione utente, il lowering produce `call`/`procedure` coerenti; per `f` **solo dichiarato** e non built-in Mnemo, si cerca `procedure f(` in `lib/*.kairos` e si include quel file.
3. **`malloc` / `free`:** compaiono nel C → si include la logica pool (`ptr_pool.kairos` + emissione `emit_ptr_pool_kairos` con `N` celle dal layout).

Se due file in `lib/` definiscono la stessa `procedure`, la compilazione fallisce con errore esplicito.

### Tabella file in `lib/`

| File | Contenuto tipico |
|------|------------------|
| `helpers.kairos` | `__mn_move_int`, helper reversibili base. |
| `mul.kairos` | `__mn_mul_into` (prodotto con somme, vincoli sui segni). |
| `divmod.kairos` | `__mn_divmod_nonneg` (divisione/resto, dividendo consumato). |
| `mod.kairos` | `__mn_mod_nonneg`. |
| `bits.kairos` | Divisione per 2, shift, AND/OR bitwise via aritmetica, `__mn_bit_k_signed`, ecc. |
| `ptr_pool.kairos` | Stub / riferimento; le procedure `__mn_pool_*` sono generate a compile-time in base a `N`. |

---

## Memoria unificata, pool e limiti Kairos

- Le “celle” del programma sono **`__mn_mem0` … `__mn_mem{N-1}`** con `N` derivato dal **layout** (variabili che vivono nel pool, dimensione richiesta da `malloc`, partizione parallela, ecc.).
- **`--ptr-pool-size`** influenza il layout quando non c’è bisogno di altro (default 4 nel CLI). Esiste un tetto **`PTR_POOL_MAX`** in `mnemo/kairos_limits.py` (allineato al lowering per programmi grandi).
- La VM Kairos ha limiti pratici su **numero di argomenti per `call`** e **parametri per procedura** (`mnemo/kairos_limits.py`: ordine di grandezza 64 argomenti, 100 parametri). Oltre quella soglia Mnemo usa **procedure pool “bancate”** (`__mn_pool_store_b0`, …) e, per le **funzioni utente** definite nello stesso file quando il pool monolitico non basta, **`maybe_inline_user_functions`** (non compatibile con l’ABI pthread a due worker sullo stesso file).

---

## Parallelismo (`mnemo_pthread_parallel*`)

Mnemo abbassa questi costrutti a **`par … and … rap`** (due thread logici Kairos):

| ABI | Uso |
|-----|-----|
| `mnemo_pthread_parallel2(a, b)` | Due worker `void (*)(void)`. |
| `mnemo_pthread_parallel2(a, b, …)` | Argomenti nell’ordine della firma C: prima tutti i parametri di `a`, poi di `b`. |
| `mnemo_pthread_parallel_with(w, c)` | Worker + continuazione. |
| `mnemo_pthread_parallel_with1(w, arg, c)` | Worker con un argomento scalare. |

**Due finestre di memoria:** se entrambi i rami riceverebbero le stesse celle `__mn_mem0…S-1`, la VM segnerebbe race. Mnemo riserva **`2·S`** celle fisiche: ramo 0 usa `0…S-1`, ramo 1 usa `S…2S-1`.

**Risultati dal secondo worker:** convenzione nomi **`__mn_p1_*`** per variabili file-scope scritte dal secondo ramo (vedi esempi in `c_examples/`).

**Mutex:** `pthread_mutex_t` a livello file diventa canale/mailbox Kairos nel modello Mnemo; per discipline di condivisione e controllo statico aggiuntivo vedi `mnemo/par_shared_mutex_check.py` e la direttiva `// mnemo-skip-par-shared-mutex-check` nei commenti del `.c` (prime ~80 righe).

---

## Direttive nel sorgente C (commenti)

| Direttiva | Effetto |
|-----------|---------|
| `// mnemo-main-argc: N` | `argc` iniziale per `int main(int argc, …)` (intero ≥ 0). Se assente, default **0**. Sovrascrivibile con `--main-argc` / `MAIN_ARGC=`. |
| `// mnemo-skip-par-shared-mutex-check` | Disattiva il controllo statico su slot condivisi + mutex nel PAR (casi avanzati; vedi messaggio nel modulo). |

---

## `argc`, `argv`

- **`argc`** è una variabile intera inizializzata come sopra.
- **`argv`** è uno **stub**: dichiarato per compatibilità sintattica ma **non** è un vero array di stringhe; non va dereferenziato come in C POSIX.

---

## `malloc`, `free`, `sizeof`

- I puntatori nel subset supportato sono **indici** nel pool (`int *`, `void *`, ecc. nel lowering).
- **`malloc(sizeof …)`** con `sizeof` costante a compile-time alloca una cella; **`free`** la restituisce.
- Modello dimensioni **stile LP32-like** per il conteggio usato con `malloc` (scalari/puntatori 4 byte nel modello interno, `char` 1), come documentato nel lowering.

---

## Subset C supportato (panorama)

### Tipi e funzioni

- `int main(void)` o `int main(int argc, char **argv)`.
- Altri tipi di ritorno per funzioni definite nel `.c`: `void`, `int`, `unsigned` / `unsigned int`, `_Bool` / `bool`, puntatori scalari (`int *`, `unsigned *`, `void *`).
- `typedef`, `struct`, `union`, `enum` (incluso `typedef struct { … } T;`).
- Parametri: scalari; array parametro `int a[N]` trattato come puntatore (decay).
- **Struct:** campi scalari e sotto-struct anonime; accesso annidato; `sizeof`.
- **Union:** solo membri scalari; `sizeof` = max dei membri.
- **Ritorno `int`:** convenzione `procedure f(..., int __mn_ret)` con ultimo argomento per il risultato.

### Puntatori e array

- Dereferenziazione e assegnamento `*p`; niente aritmetica puntatori completa.
- Array multidimensionali row-major, array di puntatori, inizializzatori; limite pratico sul numero totale di elementi (vedi errori di compilazione).

### Espressioni e istruzioni

- Aritmetica `+ - * / %`, unario `-`, `sizeof`, cast verso tipi supportati, `?:`, virgola `,`, `^` / `^=`.
- `=`, `+=`, `-=`, `*=`, `/=`, `%=`.
- `++` / `--` come istruzione su `int`.
- Chiamate, espressioni come istruzioni, assegnamenti composti.

### Controllo di flusso

- `if` / `else`, `while`, `do…while`, `for`, `break`, `continue`.
- `switch` / `case` / `default` con `break` obbligatorio a fine ramo (come da vincoli Mnemo).

### Non supportato (estratti)

- VLA, variadiche, `goto`, floating point, bit-field, indirizzi `&` oltre al modello pool, molte estensioni GCC.
- Passaggio/ritorno struct o union per valore; puntatori a struct/union oltre il subset attuale.
- Semantica UB del C pieno: valgono i vincoli delle procedure Kairos (es. divisori positivi dove richiesto).

---

## Formato IR

Definito in **`mnemo/ir.py`**: costanti, add/sub/xor in-place, swap, storia (`IHistPush`, `IStoreRev`), chiamate, costrutti Kairos (`IIfKairos`, `IFromUntilKairos`, `ILocalBlock`, `IPar`), canali, ecc.

---

## Test

```bash
make test-unit    # rapido, senza VM
make test         # richiede Kairos in KAIROS_ROOT, build-release, timeout su ogni esempio
```

I sorgenti di esempio sono in **`c_examples/`**; in root può esserci anche un `test.c` dimostrativo.

---

## Risoluzione problemi

| Sintomo | Cosa controllare |
|---------|------------------|
| Runner Kairos non trovato | `KAIROS_ROOT`, venv con `python -m src.kairos`, oppure `--kairosapp`. |
| `libvm.so` obsoleto | Nel repo Kairos: `make build-release`. |
| Errori VM su `LOCAL`/`DELOCAL` | Il Kairos emesso deve bilanciare `local`/`delocal` su ogni percorso; le librerie in `lib/` devono rispettare la VM. |
| Troppi argomenti in `call` | Ridurre celle layout, `--ptr-pool-size`, o spezzare il programma; verificare inline/banking. |

Per il **linguaggio Kairos** (reversibilità, `push`/`pop`, `if`/`fi`), fare riferimento al **README e ai test del repository Kairos**.

---

## Riferimento rapido

| Obiettivo | Comando |
|-----------|---------|
| Compilare un esempio | `mnemo compile c_examples/ex00_add_simple.c` |
| Eseguire con Make | `make run FILE=c_examples/ex00_add_simple.c` |
| Fissare `argc` | `// mnemo-main-argc: N` oppure `--main-argc N` |
| Pool più grande | `mnemo compile f.c --ptr-pool-size 32` |
| Test senza VM | `make test-unit` |
| Nuova procedura Kairos | Aggiungere `lib/mio.kairos` con `procedure nome(…)` e prototipo C coerente |

---

## Licenza e progetto

Versione pacchetto: vedi **`pyproject.toml`**. Per contribuire, mantenere allineamento con le convenzioni del codice esistente (`mnemo/c_lower.py`, `emit_kairos.py`, ecc.) e con i vincoli della VM Kairos in uso.
