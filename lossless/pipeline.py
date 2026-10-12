#!/usr/bin/env python3
"""File -> C -> Kairos VM -> file.

Reads any file, generates a C source in the Mnemo subset holding its bytes,
runs it on the reversible VM, and rebuilds the file from the decompressed bytes
the program prints. The final comparison is byte by byte.

    python3 lossless/pipeline.py img.pgm

The compression is RLE: (run length, value) pairs. Compression and
decompression are in the same program; decompression reads only the
compressed array.
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
        raise SystemExit(f"expected '{etichetta} <n>', found: {righe[0]!r}")
    k = int(testa[1])
    valori = [int(r) for r in righe[1 : 1 + k]]
    if len(valori) != k:
        raise SystemExit(f"{etichetta}: expected {k} values, read {len(valori)}")
    return bytes(valori), righe[1 + k :]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", help="file to compress (e.g. an image)")
    ap.add_argument("-o", "--out", help="where to write the rebuilt file")
    ap.add_argument("--comp", help="where to write the compressed stream")
    ap.add_argument("-c", "--csrc", help="where to keep the generated .c")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    src_path = pathlib.Path(args.file)
    dati = src_path.read_bytes()
    if not dati:
        raise SystemExit("empty file")

    csrc = pathlib.Path(args.csrc or (ROOT / "generato_rle.c"))
    csrc.write_text(genera(dati))
    print(f"input      {src_path}  {len(dati)} bytes")
    print(f"source     {csrc}")

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
        raise SystemExit(f"mnemo run failed ({proc.returncode})")

    righe = [r for r in proc.stdout.splitlines() if r.strip()]
    compresso, righe = leggi_blocco(righe, "COMP")
    ricostruito, _ = leggi_blocco(righe, "DEC")

    out_path = pathlib.Path(args.out or (ROOT / ("ricostruito_" + src_path.name)))
    out_path.write_bytes(ricostruito)
    if args.comp:
        pathlib.Path(args.comp).write_bytes(compresso)

    ok = ricostruito == dati
    print(f"VM time    {dt:.1f} s")
    print(f"compressed {len(compresso)} bytes  ({len(compresso) / len(dati):.2%} of the original)")
    print(f"rebuilt    {out_path}  {len(ricostruito)} bytes")
    print("round trip " + ("identical" if ok else "DIFFERENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
