# Mnemo — parity C / compilatore (TODO)

Backlog rispetto alla parità con un compilatore nativo (GCC). Stato: `mnemo/c_lower.py`, `mnemo/layout_collect.py`, `make test`, `c_examples/gcc_compat/`.

## Tipi e qualificatori

- [ ] **`short` / `long` / floating**: spesso riconosciuti/rifiutati; nessun float/double a runtime (vedi policy sotto).
- [x] **`char` / `const char *`**: stringhe letterali e `printf %s` estesi con test `generic_const_char_ptr.c` (modello ancora non “C pieno” per lifetime/aritmetica).
- [x] **`const` / `volatile`**: nessuna semantica C completa; molti casi accettati dal parser (qualificatori su `TypeDecl`) senza enforcement.
- [ ] **Linkage** (`static` / `extern`): una sola TU Mnemo; nessun modello linker come GCC.

## Struct / union

- [x] **Passaggio per valore**: già supportato per variabili struct (flatten campi); vedi `generic_params_by_value_*`.
- [x] **Inizializzatori `{ … }`**: struct e union in dichiarazione (liste piatte; campi in ordine, union con un solo valore).
- [ ] **Parità ABI/padding** sistematica con GCC (test a campione in `gcc_compat`).

## Operatori e lvalue

- [x] **`++` / `--`** su `x`, `*p`, `a[i]`, `s.campo`, `p->campo` (istruzione ed espressione). Test: `generic_lvalue_incdec.c`.
- [ ] Altri lvalue / espressioni assegnabili ancora limitati (`lvalue non-ID` dove non coperto).

## `switch`

- [x] Fall-through e catena `disc==v` con corpi espansi (vedi `c_lower`).
- [ ] **`break` annidato** (es. dentro `if`) verso lo stesso `switch`: **non supportato** (errore a compile time); niente schema IR reversibile ancora.

## Chiamate

- [x] **Puntatore a funzione**: solo valori risolti a **compile-time** (`f = g`, `f = &g` con `g` nota; chiamate `f(…)` e `(*f)(…)`). Layout + lowering + test `generic_func_ptr.c`.
- [x] **Variadiche user**: definizioni con `...` rifiutate; solo built-in (es. `printf`) come prima. Policy sotto.

## Documentazione

- [x] **`TODO.md`** (questo file).
- [x] **`.cursor/rules/mnemo-c-subset.mdc`**: allineato al comportamento attuale (subset, switch, ++/--, puntatori a funzione, init struct/union).
- [x] **README**: riferimento a questo TODO per backlog e limiti.

---

## Policy registrate

| Area | Decisione |
|------|-----------|
| **Floating** | Nessun `float`/`double`/`long double` a runtime: niente aritmetica IEEE; `sizeof`/usi restano rifiutati o con errore esplicito fino a nuova scelta di prodotto. |
| **Variadiche** | Nessuna funzione variadica **utente**. Solo special-case per built-in dichiarati (es. `printf`). Nessun `va_list`. |
