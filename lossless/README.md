# Compressione lossless su file reali

Un file vero entra, la VM reversibile Kairos lo comprime e lo decomprime, e il
file esce ricostruito. Serve a misurare a che dimensione arriva davvero la
catena `C -> Mnemo -> Kairos -> VM`, non a proporre un compressore competitivo.

La VM non ha filesystem: l'ingresso non puo' essere letto a runtime. Il driver
Python legge il file, genera un sorgente C che ne contiene i byte come
inizializzatore di array, esegue, e ricostruisce il file dai byte che il
programma stampa.

```
file --> pipeline.py --> generato_rle.c --> mnemo run --auto --> stdout --> file
```

## Uso

```bash
python3 lossless/pipeline.py lossless/cerchio.pgm --comp /tmp/cerchio.rle
```

Opzioni: `-o` per il file ricostruito, `--comp` per il flusso compresso, `-c`
per dove tenere il `.c` generato, `--timeout`.

## Il programma

`generato_rle.c` (prodotto dal driver) fa due cose in un solo `main`:

1. comprime `in[N]` in `out[]`, come coppie (lunghezza corsa, valore);
2. ricostruisce `back[N]` leggendo **solo** `out[0..m)`.

La decompressione non guarda l'ingresso: il confronto finale fra `back` e il
file di partenza e' quindi una verifica di losslessness, non una tautologia.

Il programma e' reversibile per intero:

```bash
mnemo run --auto --check-invertibility generato_rle.c   # uscita 0
```

`--check-invertibility` avvolge `main` in `call __main__ ; uncall __main__`: se
l'inverso non riportasse lo stato esatto di partenza, la VM fallirebbe. Passa.
L'inverso non stampa nulla di suo, quindi la decompressione resta scritta
esplicitamente nel sorgente.

## Costo

Tempo di esecuzione al crescere dei byte in ingresso, sola compressione,
`--auto`, dati con corse di lunghezza media 6:

| byte | tempo |
|---|---|
| 64 | 2,6 s |
| 128 | 11,9 s |
| 256 | 78,2 s |
| 512 | oltre 420 s |

L'esponente misurato e' circa 2,7. Il limite pratico sta quindi intorno ai
poche centinaia di byte: l'immagine di prova e' 16x16 in scala di grigi.

## Round trip sull'immagine

`cerchio.pgm`, PGM binario 16x16 (13 byte di intestazione + 256 di pixel).

```
ingresso   cerchio.pgm  269 byte
tempo VM   290,5 s
compresso  66 byte  (24,54% dell'originale)
round trip identico
```

`cmp cerchio.pgm ricostruito_cerchio.pgm` non riporta differenze.

Per riferimento, sullo stesso file: `gzip -9` produce 69 byte, `bzip2 -9` 78,
`xz -9` 112. Su un file cosi' piccolo le intestazioni pesano, e l'RLE non e'
in svantaggio. Lo stesso programma compilato con `gcc -O2` gira in circa 1 ms:
il rapporto con i 290 s della VM e' di cinque ordini di grandezza.

## File

| file | contenuto |
|---|---|
| `pipeline.py` | driver: file -> C -> VM -> file, con confronto byte a byte |
| `cerchio.pgm` | immagine di prova, 16x16 in scala di grigi |
| `generato_rle.c` | sorgente C prodotto dal driver, non versionato: lo crea la prima esecuzione |
