# Lossless compression on real files: analysis

## What was built

A complete file-to-file chain with a reversible machine in the middle:

```
cerchio.pgm --> pipeline.py --> generato_rle.c --> Mnemo --> .kairos --> Kairos VM --> stdout --> ricostruito_cerchio.pgm
```

The C program has two halves in a single `main`. The first compresses `in[N]`
into `out[]` as (run length, value) pairs. The second rebuilds `back[N]`
reading **only** `out[0..m)`, never looking at `in`. The final comparison
between `back` and the original file is therefore a real losslessness check.

One choice deserves to be stated: the VM has no filesystem, so the input cannot
be read at run time. The file's bytes go into the source as an array
initializer, and the Python driver bridges both directions. It is not a
convenience detail: it is why the program size grows with the file, as
discussed below.

## Result

`cerchio.pgm`, a 16x16 binary greyscale PGM, 269 bytes.

```
input        269 bytes
compressed    66 bytes   (24.54%)
rebuilt      269 bytes   identical according to `cmp`
VM time    290.5 s
```

The round trip closes. The compression ratio holds up against the system
compressors on the same file:

| | bytes |
|---|---|
| original | 269 |
| RLE on the Kairos VM | **66** |
| `gzip -9` | 69 |
| `bzip2 -9` | 78 |
| `xz -9` | 112 |

The comparison must be read for what it is. On 269 bytes the headers and
dictionaries of Deflate and the others weigh more than they gain, and the image
is made of long runs on purpose. The point is not that RLE beats gzip, but that
at this scale the result is not a toy.

The program also passes `--check-invertibility`, which wraps `main` in
`call __main__ ; uncall __main__`. If the inverse did not bring back the exact
initial state the VM would fail; it exits with 0. Compression and
decompression together are therefore a reversible function, not just a pair
of functions that cancel out on the data.

## Efficiency

The same `generato_rle.c` compiled with `gcc -O2` runs in about 1 ms. On the VM
it takes 290,000 times longer: five orders of magnitude. The useful question is
not how many, but **where they go**.

### It is not the compilation

Mnemo translates C to Kairos in 0.2 to 0.3 s regardless of N. All the time is
spent running.

### It is not the length of the program, it is its width

The generated `.kairos` grows like this:

| N (input bytes) | lines | bytes |
|---|---|---|
| 64 | 8,959 | 1.09 MB |
| 128 | 15,871 | 3.52 MB |
| 256 | 29,695 | 12.60 MB |
| 512 | 54,270 | 46.71 MB |

Lines double when N doubles, bytes almost quadruple. The number of
instructions is linear, their size is not. A 269-byte file produces a 12.6 MB
Kairos program.

### The cause: indexed access costs O(N)

Mnemo lowered `in[i]`, with `i` known only at run time, to a chain of
comparisons, one per cell. The following experiment isolates it: the same
number of reads, once with a runtime index (`for (i...) s += in[i];`) and once
with constant indices (`s += in[0]; s += in[1]; ...`).

| N | runtime index | constant index | ratio |
|---|---|---|---|
| 64 | 0.88 s | 0.60 s | 1.5x |
| 128 | 2.33 s | 0.75 s | 3.1x |
| 256 | 11.31 s | 1.05 s | 10.8x |

With constant indices the time goes from 0.60 s to 1.05 s while N quadruples:
less than linear, because at this scale the fixed start-up cost still
dominates. With a runtime index the same quadrupling goes from 0.88 s to
11.31 s, that is 12.9x, and the ratio between the two columns rises from 1.5x
to 10.8x. A single access does not have a constant cost: it grows with the
size of the array.

Everything else follows from this. RLE compression is a linear scan, that is
O(N) accesses, hence O(N²) work:

| N | time, compression only |
|---|---|
| 64 | 2.55 s |
| 128 | 11.93 s |
| 256 | 78.20 s |
| 512 | over 420 s |

The exponent measured between 128 and 256 is 2.71. The practical limit is just
above 250 bytes, which is exactly why the test image is 16x16.

### The same obstacle shows up on the other path

The parallel study written directly in Kairos, without going through C,
measures for the Burrows–Wheeler transform an exponent rising from 3.29 to
3.57, against the n³ stated for the naive version with arrays. There too the
extra factor n is indexed access, emulated by hand on top of stacks.

Two independent paths, the same tax. The conclusion is not about Mnemo nor
about the stack encoding: **a reversible indexed memory with constant cost is
missing**, and while it is missing every algorithm with random access pays a
factor n that has nothing to do with the algorithm.

### The counter-check: the same RLE written on stacks

The very same algorithm, on the very same 269-byte file, written directly in
Kairos with stacks instead of in C with arrays, takes 0.1 s instead of
290.5 s: three thousand times less, with the same VM.

The difference is not in the machine, it is in the data structure. RLE scans
and never jumps: on a stack it only touches the top, it stays O(n), and the VM
runs it at the expected cost. On an array with a runtime index the same scan
becomes O(n²). The stack converter reaches a 65 KB image with a verified round
trip, 244 times the data this path can handle, in a third of the time.

The comparison does not say that Kairos is better than C: it says that the
factor n is not paid by the algorithm but by indexed access, and that when the
algorithm does not need it the factor disappears. An algorithm that really
jumps, like the Burrows–Wheeler transform, pays it on both paths.

## Stated limits

- The useful size stops at a few hundred bytes. A real image, even a modest
  one, is out of reach today.
- The input goes through the source, not through a file. It follows from a VM
  without a filesystem, and it makes the program grow with the data.
- The compressed stream uses one byte per field. Packing it into bits would
  shrink the output further, but would move work to where work costs most.
- RLE is the simplest lossless compressor. It is a choice of scale, not of
  merit: a dictionary needs random access, and random access is exactly what
  cannot be afforded today.

## Next steps

**Reversible indexed memory as a VM primitive.** It is the only change that
alters the order of magnitude instead of the factor. A constant-cost
`load`/`store` pair, with its history for the inverse, removes the factor n
from both paths. The 512 bytes that today exceed 420 s would come back to
seconds, opening the kilobyte range, where an image starts being an image.

**Parallel blocks.** RLE partitions without friction: every block is
independent and the boundaries never touch. The Kairos-side study measures
2.33x on 8 blocks with `par`. Here it would give the same, and it would be the
first time reversibility and concurrency are seen together on a real file.

**LZW once indexing is O(1).** The dictionary needs random lookups; today each
lookup costs as much as the dictionary. With indexed memory it becomes the
natural candidate, with ratios RLE cannot approach on non-synthetic data.

**Reading files in the VM.** A primitive that reads bytes from a file would
decouple the program size from the data size. Today the two are tied, and 269
bytes become 12.6 MB of bytecode.

**Bit-packing the output.** Run lengths rarely exceed a few dozen: five bits
are almost always enough. It is worth it only after the per-access cost has
come down.

**Format conversion with `call` and `uncall`.** A single program that
recognizes the file type and chooses the direction: format A in input, `call`;
format B, `uncall`; the output is the file in the other format. It is the case
where reversibility is not a check but the mechanism itself: the decoder is
not written, it is obtained.
