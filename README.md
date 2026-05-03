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
| **Inclusione automatica** | (1) **Operazioni:** se nel `.c` compaiono `*`, `/`, `%`, Mnemo aggiunge `mul` / `helpers`+`divmod` o `mod`, ecc. I cicli `for` / `while` / `do…while` non richiedono più `mul.kairos` da soli (l’azzeramento del contatore di condizione reversibile usa solo storia + `+= 0`). (2) **Chiamate:** per ogni `f(...)` il cui nome **`f` non è definito** nel `.c` (solo dichiarato o usato come esterno) e **`f` non è** una built-in interna (`__mn_*`), Mnemo **scansiona** tutti i file in `lib/*.kairos`, trova le righe `procedure f(…)` e **include** il file che definisce `f`. Aggiungi procedure in `lib/mio.kairos` e un prototipo C `void f(...);` / `int f(...);` coerente: non serve alcuna direttiva. (3) **`malloc` / `free`:** se compaiono, si include anche **`ptr_pool.kairos`** e si generano le celle di memoria simulata (vedi sotto). |
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
mnemo compile sorgente.c --ptr-pool-size N  # celle per malloc/free (default 4, max 256)

mnemo run sorgente.c
mnemo run sorgente.c --main-argc 7
mnemo run sorgente.c --ptr-pool-size 16
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
  - **`argv`** è uno **stub**: dichiarato come `int` e **sempre 0**. Non sono stringhe né puntatori veri; non si dereferenzia.

Per provare valori diversi senza toccare il sorgente:  
`mnemo compile file.c --main-argc 7` oppure `make run FILE=file.c MAIN_ARGC=7`.

---

## Pool puntatori, `malloc` e `free`

- I valori “puntatore” sono **indici interi** in un pool di celle **`__mn_mem0` … `__mn_mem{N-1}`** con **`N = --ptr-pool-size`** (default **4**, massimo **256**).
- **`malloc(sizeof …)`** (con `sizeof` costante a compile-time) alloca una cella libera; **`free(p)`** la restituisce al pool.
- **`sizeof`** per tipi/variabili supportati è calcolato a **compile-time** (modello **LP32-like**: `char` 1 byte, scalari e puntatori 4 byte per il conteggio usato con `malloc`).

---

## Parallelismo (`mnemo_pthread_parallel*`)

Mnemo abbassa questi prototipi su **`par … and … rap`** nella VM Kairos (due thread logici):

| ABI | Effetto |
|-----|---------|
| **`mnemo_pthread_parallel2(a,b)`** | `par call a … and call b … rap` con `void a(void)`, `void b(void)`. |
| **`mnemo_pthread_parallel2(a,b, …)`** | Dopo `a` e `b` vengono gli argomenti **nell’ordine della firma C**: prima tutti quelli di `a`, poi tutti quelli di `b` (scalari, struct per valore, puntatori, … — come in una chiamata normale). Esempio: `void a(int x, mps_t *p)` e `void b(mps_t *q, int k)` → `parallel2(a, b, x, p, q, k)`. Regione mem 0 / 1 come sopra. |
| **`mnemo_pthread_parallel_with(w,c)`** | worker `w` e continuazione `c` insieme (`void (*)(void)` entrambi). |
| **`mnemo_pthread_parallel_with1(w, arg, c)`** | Come sopra con argomento scalare verso `w`. |

**Due finestre di memoria.** Due chiamate che ricevono gli **stessi** parametri `__mn_mem0 … __mn_mem{S-1}` nel ramo `PAR` creano una race nel controllo statico Kairos. Il compilatore Mnemo, quando incontra uno degli ABI sopra, riserva **`2·S`** celle fisiche (`S` = layout unificato del programma) e passa al primo ramo `__mn_mem0 … __mn_mem{S-1}` e al secondo **`__mn_mem{S} … __mn_mem{2S-1}`**. Il pool `__mn_pool_*` resta definito su **una** finestra di **S** argomenti per chiamata (ogni worker ha la sua copia logica).

**Risultati dai worker al `main` (variabili file-scope).** Puoi dichiarare **`int nome;`** a livello file (prima delle funzioni). Il worker del **primo** ramo (`parallel2`: prima funzione; `parallel_with*`: la *continuazione* è sul ramo 0) scrive in variabili file normali: stessa cella che il `main` vede come `__mn_mem{idx}`. Per l’uscita del **secondo** ramo usa un nome che inizia per **`__mn_p1_`** (es. `int __mn_p1_sum;`): nel worker è il formale `__mn_mem{idx}`, nel `main` è la cella **`__mn_mem{S+idx}`** dopo il `rap`. Esempio completo: **`c_examples/ex33_parallel2_fib.c`** e **`test.c`** in root.

**Nota:** variabili **`pthread_mutex_t`** restano canali **locali alla procedura** Kairos; per messaggi tra procedure servirebbe altro modello.

---

## Direttive nel sorgente C

### (Nessuna direttiva per le lib)

Le procedure Kairos in **`mnemo/lib/`** vengono incluse **automaticamente** quando il tuo C le **chiama** (nome della `procedure` uguale al nome della funzione nel prototipo/chiamata) oppure quando servono per `* / %`, cicli, o pool puntatori. Nel `.c` serve solo un **prototipo C valido** (`void f(int x);`, `int g(void);`, …) così il parser accetta `f(…);` / `x = g();`.

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
| `ptr_pool.kairos` | `__mn_pool_*` — allocazione LIFO, load/store, `free` sul pool. |

Gli esempi sono in **`c_examples/`** (`ex21` cicli/condizioni/main, `ex22`–`ex26` puntatori/array/`sizeof`, `ex27`–`ex28` typedef/struct/enum/union/ternario/…, `ex33`–`ex34` parallelismo / sketch client-server, **`test.c`** in root come vetrina compatta).

---

## Subset C supportato (riepilogo)

### Tipi e funzioni

- **`int main(void)`** oppure **`int main(int argc, char **argv)`** (unico `main`).
- **Altri tipi di ritorno** per funzioni definite nel `.c`: `void`, `int`, `unsigned`/`unsigned int`, `_Bool`, `bool`, **`void *`** / **`int *`** (valore = indice pool).
- **`typedef`**: alias per tipi già supportati (es. `typedef unsigned int uint;`), **`struct`**, **`union`**, **`enum`** (incluso `typedef struct/union/enum { … } T;`).
- **`enum`**: costanti intere (`A`, `B = 3`, …); nei **`case`** dello **`switch`** si possono usare **costanti o enumeratori**.
- **Parametri**: scalari come sopra; **`int a[N]`** come parametro è trattato come **`int *`** (decay); puntatori **`int *`**, **`unsigned *`**, **`void *`**; niente VLA né tipi aggiuntivi arbitrari.
- **Struct**: campi **scalari** e **sotto-struct anonime** in linea (`struct { int y; } n;` → accesso `s.n.y`, nomi interni piatti tipo `s__n__y`). Accesso annidato **`a.b.c`**; **`sizeof(struct Tag)`** e **`sizeof`** variabile struct.
- **Union**: solo membri **scalari**; tutti i membri condividono **una** variabile Kairos (`sizeof` = max dei membri); accesso **`u.x`** (nessun membro struct/union annidato).
- **Convenzione ritorno `int`**: `int foo(int a)` → `procedure foo(int a, int __mn_ret)`; il chiamante passa un ultimo argomento azzerato che riceve il risultato.

### Puntatori e array

- **Puntatori** a `int` / `unsigned` / `void` (un livello di `*` nel subset); dereferenziazione **`*p`**, assegnamento **`*p = …`**. Nessun aritmetica puntatori completa (`p+1` non è modellata come in C).
- **Array**: `int a[N]`, multidimensionale **`int m[R][C]`** (row-major), array di puntatori **`int *p[K]`**, **`void *v[K]`**, **`unsigned *`**, con indici e init **`{ … }`** piatto o annidato. **Massimo 256 elementi** totali per array (prodotto delle dimensioni).
- **`sizeof`**: tipo tra parentesi o nome variabile/array/puntatore/struttura (ove supportato).

### Espressioni e assegnamenti

- Letterali intere, identificatori, `+ - * / %`, unario `-`, `sizeof`, cast verso gli scalari/puntatori elencati; operatore **ternario** **`?:`**; operatore **virgola** `,` (anche forma parser **`ExprList`** negli initializer, es. `int x = (a, b);`); XOR **`^`** e **`^=`** (anche su campo union).
- **Espressione come istruzione**: chiamate `void`, incrementi, **`(void)x;`** o più in generale **`(tipo)expr;`** con risultato ignorato (valutazione + scarto reversibile dei temporanei).
- Chiamate `f(...)` con `void` o valore `int` usato in assegnamento / espressione.
- **`=`** e assegnamenti composti **`+=`, `-=`, `*=`, `/=`, `%=`**, **`^=`** (desugar su binop + assegnamento).
- **`++` / `--`** su variabile `int` come **istruzione** (incluso incremento del `for`), con lowering reversibile corretto.

### Controllo di flusso

- **`if` / `else`**: confronti `== != < <= > >=`, `!`, truthiness su `int` (`!= 0`), **`&&` e `||`** con cortocircuito.
- **`while`**, **`do…while`**, **`for`** (init dichiarazione o espressione, condizione, step `i++` ecc.).
- **`break`** nei **cicli** e **`continue`**; **`switch`**: `case` con costante intera o **enumeratore**, **`break` obbligatorio in coda a ogni ramo**, **`default` ultimo**.

### `main` e `return`

- In **`main`**, `return` con valore **diverso da `0`** è ignorato per la VM (stile esempi); `return 0;` è il caso “pulito”.

### Limitazioni importanti (non è C completo)

- **VLA**, variadiche, **`goto`**.
- **Float / double**, **bit-field**, aritmetica puntatori reale, **`&` (indirizzi)** oltre al modello pool.
- **Union/struct** con membri annidati non scalari; niente **passaggio/ritorno** di struct o union per valore; niente **puntatori a struct/union** nel subset attuale.
- Preprocessore: quanto emerge da **`gcc -E`**.
- Semantica C su UB e segni: restano i vincoli delle procedure Kairos (es. divisione/modulo con divisore positivo dove richiesto).

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
| Pool più grande per `malloc` | `mnemo compile f.c --ptr-pool-size 32` |
| Test rapidi (lowering, senza VM) | `make test-unit` |
| Lib Kairos custom | Metti `procedure nome(…)` in `lib/qualcosa.kairos` e dichiara `nome` in C; Mnemo include il file da solo |

Per domande sul linguaggio Kairos (reversibilità, `push`/`pop`, `if`/`fi`), vedi la documentazione nella **root del repo Kairos** (`README.md` e test di errore statico).
