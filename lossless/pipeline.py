#!/usr/bin/env python3
"""File -> C -> Kairos VM -> file.

Legge un file qualunque, genera un sorgente C nel subset Mnemo che ne contiene
i byte, lo esegue sulla VM reversibile, e ricostruisce il file dai byte
decompressi che il programma stampa. Il confronto finale e' byte a byte.

    python3 lossless/pipeline.py img.pgm

La compressione e' RLE: coppie (lunghezza corsa, valore). Compressione e
decompressione stanno nello stesso programma; la decompressione legge solo
l'array compresso.
"""

import argparse
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
MNEMO = ROOT.parent / ".venv" / "bin" / "mnemo"

TEMPLATE = """\
#include <stdio.h>

/* Compressione lossless RLE su un blocco di byte, con la decompressione
   ricalcolata dal solo array compresso. I byte del file sono nel sorgente:
   la VM Kairos non ha filesystem, l'ingresso arriva dal generatore. */

#define N {n}
#define MAXOUT {maxout}

int main(void) {{
    unsigned char in[N] = {{{data}}};
    unsigned char out[MAXOUT];
    unsigned char back[N];

    /* --- compressione --- */
    int m = 0;
    int i = 0;
    while (i < N) {{
        int run = 1;
        while (i + run < N && in[i + run] == in[i] && run < 255) {{
            run++;
        }}
        out[m] = (unsigned char)run;
        m++;
        out[m] = in[i];
        m++;
        i += run;
    }}

    printf("COMP %d\\n", m);
    for (int k = 0; k < m; k++) {{
        printf("%d\\n", out[k]);
    }}

    /* --- decompressione: legge solo out[0..m) --- */
    int p = 0;
    int k2 = 0;
    while (k2 < m) {{
        int run = out[k2];
        unsigned char v = out[k2 + 1];
        int j = 0;
        while (j < run) {{
            back[p] = v;
            p++;
            j++;
        }}
        k2 += 2;
    }}

    printf("DEC %d\\n", p);
    for (int k = 0; k < p; k++) {{
        printf("%d\\n", back[k]);
    }}
    return 0;
}}
"""


def genera(data: bytes) -> str:
    n = len(data)
    return TEMPLATE.format(
        n=n,
        maxout=2 * n,
        data=",".join(str(b) for b in data),
    )


def leggi_blocco(righe, etichetta):
    """Consuma '<etichetta> <k>' seguito da k interi. Ritorna (bytes, resto)."""
    testa = righe[0].split()
    if len(testa) != 2 or testa[0] != etichetta:
        raise SystemExit(f"atteso '{etichetta} <n>', trovato: {righe[0]!r}")
    k = int(testa[1])
    valori = [int(r) for r in righe[1 : 1 + k]]
    if len(valori) != k:
        raise SystemExit(f"{etichetta}: attesi {k} valori, letti {len(valori)}")
    return bytes(valori), righe[1 + k :]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", help="file da comprimere (es. un'immagine)")
    ap.add_argument("-o", "--out", help="dove riscrivere il file ricostruito")
    ap.add_argument("--comp", help="dove scrivere il flusso compresso")
    ap.add_argument("-c", "--csrc", help="dove tenere il .c generato")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    src_path = pathlib.Path(args.file)
    dati = src_path.read_bytes()
    if not dati:
        raise SystemExit("file vuoto")

    csrc = pathlib.Path(args.csrc or (ROOT / "generato_rle.c"))
    csrc.write_text(genera(dati))
    print(f"ingresso   {src_path}  {len(dati)} byte")
    print(f"sorgente   {csrc}")

    t0 = time.time()
    proc = subprocess.run(
        [str(MNEMO), "run", "--auto", str(csrc)],
        capture_output=True,
        text=True,
        timeout=args.timeout,
    )
    dt = time.time() - t0
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"mnemo run fallito ({proc.returncode})")

    righe = [r for r in proc.stdout.splitlines() if r.strip()]
    compresso, righe = leggi_blocco(righe, "COMP")
    ricostruito, _ = leggi_blocco(righe, "DEC")

    out_path = pathlib.Path(args.out or (ROOT / ("ricostruito_" + src_path.name)))
    out_path.write_bytes(ricostruito)
    if args.comp:
        pathlib.Path(args.comp).write_bytes(compresso)

    ok = ricostruito == dati
    print(f"tempo VM   {dt:.1f} s")
    print(f"compresso  {len(compresso)} byte  ({len(compresso) / len(dati):.2%} dell'originale)")
    print(f"ricostr.   {out_path}  {len(ricostruito)} byte")
    print("round trip " + ("identico" if ok else "DIVERSO"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
