# Mnemo

Toolchain **IR-first** che traduce un **subset di C** reversibile in sorgente **Kairos**, da eseguire sulla VM del repo Kairos.

## Cosa fa

```
file.c  →  parse (gcc -E + pycparser)  →  IR Mnemo  →  emit  →  file.kairos
```

L’output è un unico `.kairos` che include (se servono) le procedure in `mnemo/lib/` **preposte** al `main` generato.

## Pipeline e dipendenze tra file

| Ingresso | Ruolo |
|----------|--------|
| **`lib/*.kairos`** | Libreria: moltiplicazione, divisione/resto, helper (`__mn_mul_into`, …). |
| **Inclusione automatica** | (1) **Operazioni e cicli:** se nel `.c` compaiono `*`, `/`, `%` o cicli `for` / `while` / `do…while`, Mnemo aggiunge `mul` / `helpers`+`divmod` o `mod`, ecc. (i cicli usano `mul.kairos` per il contatore di condizione reversibile). (2) **Chiamate:** per ogni `f(...)` il cui nome **`f` non è definito** nel `.c` (solo dichiarato o usato come esterno) e **`f` non è** una built-in interna (`__mn_*`), Mnemo **scansiona** tutti i file in `lib/*.kairos`, trova le righe `procedure f(…)` e **include** il file che definisce `f`. Aggiungi procedure in `lib/mio.kairos` e un prototipo C `void f(...);` / `int f(...);` coerente: non serve alcuna direttiva. |
| **`// mnemo-main-argc: N`** | Opzionale: valore iniziale di `argc` quando usi `int main(int argc, …)`. Se **manca**, il default è **0** (vedi sotto). |

**`mnemo compile`** scrive **`stem.kairos` nella stessa cartella del `.c`** (salvo `-o`).  
**`mnemo run`** compila e avvia l’eseguibile Kairos configurato (vedi CLI).

## Installazione (sviluppo)

Mnemo è un **repository a sé**. La **VM Kairos** (`python -m src.kairos`) resta nel repo Kairos, con il suo `venv/`.

Layout consigliato (stessa directory padre):

```text
Desktop/mnemo/    ← questo repo
Desktop/kairos/   ← clone del repo Kairos (con `venv/` e `src/kairos`)
```

Il `Makefile` usa **`KAIROS_ROOT`**, default **`$(pwd)/../kairos`**. Se la VM è altrove:

```bash
export KAIROS_ROOT=/percorso/al/repo/kairos
make test
```

Dopo aver **spostato** la cartella Mnemo, ricrea il venv: `rm -rf .venv && make venv`.

```bash
cd mnemo    # root del clone Mnemo
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
make test   # opzionale: compile c_examples + esegue ogni .kairos sulla VM
```

Se vedi **`No such file or directory`** su `mnemo` e un path tipo `.../kairos/mnemo/.venv`, hai ancora attiva una **venv vecchia**: `deactivate`, `hash -r`, poi `cd` nella nuova root e `source .venv/bin/activate` (venv ricreato lì come sopra).

### Requisiti

- **`gcc`** nel PATH (preprocessore C per pycparser).
- **`pycparser`** (dipendenza del pacchetto).
- Per **`make test`** / **`make run`**: Python della VM in **`$KAIROS_ROOT/venv/bin/python`** (nel repo Kairos: `make install-deps` o equivalente).

## CLI

```bash
mnemo compile sorgente.c                    # → sorgente.kairos accanto al .c
mnemo compile sorgente.c -o out.kairos
mnemo compile sorgente.c --stdout           # stampa il Kairos su stdout
mnemo compile sorgente.c --main-argc 7      # sovrascrive argc (vedi sotto)

mnemo run sorgente.c
mnemo run sorgente.c --main-argc 7
mnemo run sorgente.c --kairosapp /path/to/kairosapp
```

Variabile **`MNEMO_KAIROSAPP`**: eseguibile usato da `mnemo run` se non passi `--kairosapp`.

## `make` (cartella `mnemo/`)

```bash
make help           # riepilogo comandi
make venv           # prima volta: .venv + pip install -e .
make compile        # mnemo compile su tutti c_examples/*.c
make run FILE=c_examples/ex01_mul_small.c
make run FILE=c_examples/ex21_loops_cond_main.c MAIN_ARGC=7   # come --main-argc 7
make test           # compile + esegue ogni .kairos (timeout 5s, controlli errore VM)
make clean-kairos   # rimuove c_examples/*.kairos
```

`FILE=` accetta un `.c` (ricompila) o un `.kairos` già generato.  
**Attenzione:** `make run FILE=foo.c 7` è **sbagliato**: Make interpreta `7` come secondo target. Usa `MAIN_ARGC=7` senza spazio extra.

Se tieni ancora un **monorepo** che wrappa Mnemo e Kairos, puoi avere target lì; in setup standalone usa solo il `Makefile` di questo repo e **`KAIROS_ROOT`**.

---

## `argc`, `argv` e “input”

Kairos **non** espone la riga di comando del processo come un C normale su OS.

- **`int main(int argc, char **argv)`** è supportata così:
  - **`argc`** è una variabile `int` locale inizializzata da:
    1. **`// mnemo-main-argc: N`** nel `.c` (se presente), altrimenti **0**;
    2. oppure **`mnemo compile --main-argc N`** / **`make run … MAIN_ARGC=N`**, che **sostituiscono** il valore della direttiva.
  - **`argv`** è uno **stub**: dichiarato come `int` e **sempre 0**. Non sono stringhe né puntatori; non si può dereferenziare.

Per provare valori diversi senza toccare il sorgente:  
`mnemo compile file.c --main-argc 7` oppure `make run FILE=file.c MAIN_ARGC=7`.

---

## Direttive nel sorgente C

### (Nessuna direttiva per le lib)

Le procedure Kairos in **`mnemo/lib/`** vengono incluse **automaticamente** quando il tuo C le **chiama** (nome della `procedure` uguale al nome della funzione nel prototipo/chiamata) oppure quando servono per `* / %` o per i cicli. Nel `.c` serve solo un **prototipo C valido** (`void f(int x);`, `int g(void);`, …) così il parser accetta `f(…);` / `x = g();`.

Se due file in `lib/` definiscono la stessa `procedure foo`, la compilazione fallisce con un errore esplicito.

### `// mnemo-main-argc: N`

Solo per `main` con `int argc`: fissa **`argc`** a **N** a compile-time (intero non negativo), a meno che non passi `--main-argc` / `MAIN_ARGC=`.

---

## Librerie `lib/`

| File | Ruolo |
|------|--------|
| `helpers.kairos` | Copie / helper reversibili (`__mn_move_int`, …). |
| `mul.kairos` | `__mn_mul_into` — prodotto con somme (`dst += a*b`, `b >= 0`). |
| `divmod.kairos` | `__mn_divmod_nonneg` — quoziente e resto (`a>=0`, `b>0`). |
| `mod.kairos` | `__mn_mod_nonneg` — resto. |

Gli esempi sono in **`c_examples/`** (`ex21` illustra `for`, `continue`, `break`, `&&`, `main(argc,argv)`, …).

---

## Subset C supportato (riepilogo)

### Tipi e funzioni

- **`int main(void)`** oppure **`int main(int argc, char **argv)`** (unico `main`).
- **Altri tipi di ritorno** per funzioni definite nel `.c`: `void`, `int`, `unsigned`/`unsigned int`, `_Bool`, `bool` — in Kairos sono tutti **`int`** per i valori numerici.
- **Parametri**: solo scalari come sopra (niente puntatori veri, tratto `argv` come eccezione documentata stub).
- **Convenzione ritorno `int`**: `int foo(int a)` → `procedure foo(int a, int __mn_ret)`; il chiamante passa un ultimo argomento azzerato che riceve il risultato.

### Espressioni e assegnamenti

- Letterali intere, identificatori, `+ - * / %`, unario `-`, cast verso gli scalari elencati.
- Chiamate `f(...)` con `void` o valore `int` usato in assegnamento / espressione.
- **`=`** e assegnamenti composti **`+=`, `-=`, `*=`, `/=`, `%=`** (desugar su binop + assegnamento).
- **`++` / `--`** su variabile `int` come **istruzione** (incluso incremento del `for`), con lowering reversibile corretto (`i++` non è “azzera `i` e poi +=1”).

### Controllo di flusso

- **`if` / `else`**: confronti `== != < <= > >=`, `!`, truthiness su `int` (`!= 0`), **`&&` e `||`** con cortocircuito (traduzione in `if` annidati / catene).
- **`while`**, **`do…while`**, **`for`** (init dichiarazione o espressione, condizione, step `i++` ecc.).
- **`break`** nei **cicli** (esce dal ciclo più interno che lo gestisce; non confondere con `break` nel `switch`).
- **`continue`** nei cicli; supportato anche nella forma **`if (cond) continue;`** (non solo `continue` top-level nel blocco).
- **`switch`**: solo `case` con costante intera, **`break` obbligatorio in coda a ogni ramo** (niente fall-through), **`default` ultimo**. Il `break` del `case` **non** è il `break` del ciclo che avvolge lo `switch` (Mnemo distingue i due casi).

### `main` e `return`

- In **`main`**, `return` con valore **diverso da `0`** è ignorato per la VM (stile esempi); `return 0;` è il caso “pulito”.

### Limitazioni importanti (non è C completo)

- Niente **`struct` / `union` / `enum`**, array, puntatori reali (oltre alla firma stub di `argv`), **`sizeof`**, variadiche, **`goto`**.
- **`&&` / `||`** solo dove il lowering li supporta (condizioni `if` e condizioni di ciclo tramite contatore interno).
- Semantica C su UB e segni: restano i vincoli delle procedure Kairos (es. divisione/modulo con divisore positivo dove richiesto).
- Preprocessore: quanto emerge da **`gcc -E`** per il parse.

---

## Formato IR

La rappresentazione intermedia vive in **`mnemo/ir.py`** (istruzioni, `Function`, `Program`, confronti, `if`/`fi`, `from`/`until`, `local`/`delocal`, storia, chiamate).

---

## Riferimenti rapidi

| Voglio… | Come |
|--------|------|
| Compilare un esempio | `mnemo compile c_examples/ex00_add_simple.c` |
| Eseguire dalla cartella Mnemo con la VM Kairos | `make run FILE=c_examples/ex00_add_simple.c` |
| Fissare `argc` nel sorgente | prima riga: `// mnemo-main-argc: 4` |
| Fissare `argc` da CLI | `mnemo compile f.c --main-argc 4` o `make run FILE=f.c MAIN_ARGC=4` |
| Default `argc` senza direttiva | **0** |
| Lib Kairos custom | Metti `procedure nome(…)` in `lib/qualcosa.kairos` e dichiara `nome` in C; Mnemo include il file da solo |

Per domande sul linguaggio Kairos (reversibilità, `push`/`pop`, `if`/`fi`), vedi la documentazione nella **root del repo Kairos** (`README.md` e test di errore statico).
