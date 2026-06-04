# c_probe — corpus di test gcc-vs-mnemo 1:1

Programmi C (subset Mnemo) per verificare l'equivalenza output con gcc.

- `t/*.c` — i test (generati da `gen*.py`, + aggiunte manuali).
- `run.sh [dir]` — compila ogni file con gcc e con mnemo, confronta stdout.
  Salta i file con `// SKIP` come prima riga.
- Stato: 152/154 PASS (2 SKIP documentati: fn-ptr param, struct-array annidato
  con campo-array; + alcuni SKIP per UB/unspecified: overflow int signed,
  sizeof(ptr), ordine valutazione argomenti).

Rigenerare: `python3 gen.py && python3 gen2.py && python3 gen3.py`.
