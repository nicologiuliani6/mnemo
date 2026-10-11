# Lossless compression on real files

A real file goes in, the reversible Kairos VM compresses and decompresses it,
and the file comes out rebuilt. The point is to measure how far the
`C -> Mnemo -> Kairos -> VM` chain actually scales, not to propose a
competitive compressor.

The VM has no filesystem: the input cannot be read at run time. The Python
driver reads the file, generates a C source holding its bytes as an array
initialiser, runs it, and rebuilds the file from the bytes the program prints.

```
file --> pipeline.py --> generato_rle.c --> mnemo run --auto --> stdout --> file
```

## Usage

```bash
python3 lossless/pipeline.py lossless/cerchio.pgm --comp /tmp/cerchio.rle
```

Options: `-o` for the rebuilt file, `--comp` for the compressed stream, `-c`
for where to keep the generated `.c`, `--timeout`.

## The program

`generato_rle.c` (produced by the driver) does two things in a single `main`:

1. compresses `in[N]` into `out[]`, as (run length, value) pairs;
2. rebuilds `back[N]` reading **only** `out[0..m)`.

Decompression never looks at the input: the final comparison between `back`
and the original file is therefore a losslessness check, not a tautology.

The whole program is reversible:

```bash
mnemo run --auto --check-invertibility generato_rle.c   # exit 0
```

`--check-invertibility` wraps `main` in `call __main__ ; uncall __main__`: if
the inverse did not bring back the exact initial state, the VM would fail. It
passes. The inverse prints nothing of its own, so decompression stays
explicitly written in the source.

## Cost

Run time as the input grows, compression only, `--auto`, data with an average
run length of 6:

| bytes | time |
|---|---|
| 64 | 2.6 s |
| 128 | 11.9 s |
| 256 | 78.2 s |
| 512 | over 420 s |

The measured exponent is about 2.7, so the practical limit is a few hundred
bytes: the test image is 16x16 greyscale.

## Round trip on the image

`cerchio.pgm`, binary PGM 16x16 (13 header bytes + 256 pixels).

```
input        cerchio.pgm  269 bytes
VM time      290.5 s
compressed   66 bytes  (24.54% of the original)
round trip   identical
```

`cmp cerchio.pgm ricostruito_cerchio.pgm` reports no differences.

For reference, on the same file: `gzip -9` produces 69 bytes, `bzip2 -9` 78,
`xz -9` 112. On such a small file headers dominate and RLE is not at a
disadvantage. The same program compiled with `gcc -O2` runs in about 1 ms: the
ratio to the VM's 290 s is five orders of magnitude.

## Files

| file | content |
|---|---|
| `pipeline.py` | driver: file -> C -> VM -> file, with byte-by-byte comparison |
| `cerchio.pgm` | test image, 16x16 greyscale |
| `generato_rle.c` | C source produced by the driver, not tracked: the first run creates it |
