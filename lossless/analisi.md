# Compressione lossless su file reali: analisi

## Che cosa si è costruito

Una catena completa da file a file, con al centro una macchina reversibile:

```
cerchio.pgm --> pipeline.py --> generato_rle.c --> Mnemo --> .kairos --> VM Kairos --> stdout --> ricostruito_cerchio.pgm
```

Il programma C ha due metà in un solo `main`. La prima comprime `in[N]` in
`out[]` come coppie (lunghezza corsa, valore). La seconda ricostruisce `back[N]`
leggendo **solo** `out[0..m)`, senza mai guardare `in`. Il confronto finale fra
`back` e il file di partenza è quindi una verifica vera di losslessness.

Una scelta merita di essere dichiarata: la VM non ha filesystem, quindi
l'ingresso non può essere letto a runtime. I byte del file finiscono nel
sorgente come inizializzatore di array, e il driver Python fa da ponte in
entrambe le direzioni. Non è un dettaglio di comodo: è la ragione per cui la
dimensione del programma cresce col file, e su questo si torna sotto.

## Risultato

`cerchio.pgm`, PGM binario 16x16 in scala di grigi, 269 byte.

```
ingresso   269 byte
compresso   66 byte   (24,54%)
ricostruito 269 byte  identico a `cmp`
tempo VM   290,5 s
```

Il round trip chiude. Il rapporto di compressione regge il confronto con i
compressori di sistema sullo stesso file:

| | byte |
|---|---|
| originale | 269 |
| RLE su VM Kairos | **66** |
| `gzip -9` | 69 |
| `bzip2 -9` | 78 |
| `xz -9` | 112 |

Il confronto va letto per quello che è. Su 269 byte le intestazioni e i
dizionari di Deflate e degli altri pesano più di quanto rendano, e l'immagine
è fatta apposta di corse lunghe. Non si sta dicendo che l'RLE batte gzip: si
sta dicendo che a questa scala il risultato non è un giocattolo.

Il programma passa anche `--check-invertibility`, che avvolge `main` in
`call __main__ ; uncall __main__`. Se l'inverso non riportasse lo stato esatto
di partenza la VM fallirebbe; esce 0. Compressione e decompressione insieme
sono quindi una funzione reversibile, non solo una coppia di funzioni che si
annullano sui dati.

## Efficienza

Lo stesso `generato_rle.c` compilato con `gcc -O2` gira in circa 1 ms. Sulla VM
ne servono 290.000. Cinque ordini di grandezza. La domanda utile non è quanti,
ma **dove finiscono**.

### Non è la compilazione

Mnemo traduce da C a Kairos in 0,2 s a 0,3 s indipendentemente da N. Tutto il
tempo sta nell'esecuzione.

### Non è la lunghezza del programma, è la sua larghezza

Il `.kairos` generato cresce così:

| N (byte in ingresso) | righe | byte |
|---|---|---|
| 64 | 8.959 | 1,09 MB |
| 128 | 15.871 | 3,52 MB |
| 256 | 29.695 | 12,60 MB |
| 512 | 54.270 | 46,71 MB |

Le righe raddoppiano quando N raddoppia, i byte quasi quadruplicano. Il numero
di istruzioni è lineare, la loro dimensione no. Un file di 269 byte produce un
programma Kairos di 12,6 MB.

### La causa: l'accesso per indice costa O(N)

Mnemo abbassa `in[i]` con `i` noto solo a runtime in una catena di confronti,
una per cella. L'esperimento seguente lo isola: stesso numero di letture,
una volta con indice a runtime (`for (i...) s += in[i];`) e una volta con
indice costante (`s += in[0]; s += in[1]; ...`).

| N | indice a runtime | indice costante | rapporto |
|---|---|---|---|
| 64 | 0,88 s | 0,60 s | 1,5x |
| 128 | 2,33 s | 0,75 s | 3,1x |
| 256 | 11,31 s | 1,05 s | 10,8x |

Con indice costante il tempo passa da 0,60 s a 1,05 s mentre N quadruplica:
cresce meno che linearmente, perché a questa scala lo domina ancora il costo
fisso di avvio. Con indice a runtime lo stesso quadruplicamento porta da 0,88 s
a 11,31 s, cioè 12,9x, e il rapporto fra le due colonne sale da 1,5x a 10,8x.
Il singolo accesso non ha costo costante: cresce con la dimensione dell'array.

Da qui segue tutto il resto. La compressione RLE fa una scansione lineare, cioè
O(N) accessi, quindi O(N²) lavoro:

| N | tempo, sola compressione |
|---|---|
| 64 | 2,55 s |
| 128 | 11,93 s |
| 256 | 78,20 s |
| 512 | oltre 420 s |

L'esponente misurato fra 128 e 256 è 2,71. Il limite pratico sta poco sopra i
250 byte, che è esattamente il motivo per cui l'immagine di prova è 16x16.

### Lo stesso ostacolo si ritrova per l'altra strada

Lo studio parallelo scritto direttamente in Kairos, senza passare da C, misura
per la trasformata di Burrows e Wheeler un esponente che sale da 3,29 a 3,57
contro l'n³ dichiarato per la versione ingenua con gli array. Anche lì il
fattore n in più è l'accesso per indice, lì emulato a mano sopra gli stack.

Due percorsi indipendenti, la stessa tassa. La conclusione non è su Mnemo né
sulla codifica a stack: è che **manca una memoria indicizzata reversibile a
costo costante**, e finché manca ogni algoritmo che accede a caso paga un
fattore n che non ha nulla a che vedere con l'algoritmo.

### La controprova: lo stesso RLE scritto su stack

Lo stesso identico algoritmo, sullo stesso identico file da 269 byte, scritto
direttamente in Kairos con gli stack invece che in C con gli array, costa 0,1 s
invece di 290,5 s. Tremila volte, con la stessa VM.

La differenza non è nella macchina, è nella struttura dati. L'RLE scorre e non
salta: su stack tocca solo la cima, resta O(n), e la VM lo esegue al costo che
ci si aspetta. Su array con indice a runtime la stessa scansione diventa O(n²).
Il convertitore su stack arriva a 65 KB di immagine con giro completo
verificato, cioè 244 volte il dato che regge questa strada, in un terzo del
tempo.

Il confronto non dice che Kairos è meglio di C: dice che il fattore n non lo
paga l'algoritmo, lo paga l'accesso indicizzato, e che quando l'algoritmo non
ne ha bisogno il fattore sparisce. Un algoritmo che salta davvero, come la
trasformata di Burrows e Wheeler, lo paga su entrambe le strade.

## Limiti dichiarati

- La dimensione utile si ferma a poche centinaia di byte. Un'immagine vera,
  anche modesta, è fuori portata oggi.
- L'ingresso passa dal sorgente, non da un file. È una conseguenza della VM
  senza filesystem, e fa crescere il programma con il dato.
- Il flusso compresso è un byte per campo. Impacchettarlo in bit ridurrebbe
  ancora l'uscita, ma sposterebbe lavoro dove il lavoro costa di più.
- L'RLE è il compressore più semplice che sia lossless. È una scelta di
  scala, non di merito: un dizionario chiede accesso casuale, e l'accesso
  casuale è proprio la cosa che oggi non si può permettere.

## Sviluppi

**Memoria indicizzata reversibile come primitiva della VM.** È l'unico
intervento che cambia l'ordine di grandezza invece del fattore. Una coppia
`load`/`store` a costo costante, con la sua storia per l'inversione, toglie il
fattore n a entrambi i percorsi. I 512 byte che oggi sfondano i 420 s
tornerebbero nell'ordine dei secondi, e con essi si aprirebbe la fascia dei
kilobyte, dove un'immagine comincia a essere un'immagine.

**Blocchi in parallelo.** L'RLE si partiziona senza attriti: ogni blocco è
indipendente e i confini non si toccano. Lo studio lato Kairos misura 2,33x su
8 blocchi con `par`. Qui darebbe lo stesso, e sarebbe la prima volta che
reversibilità e concorrenza si vedono insieme su un file vero.

**LZW quando l'indicizzazione sarà O(1).** Il dizionario chiede lookup a caso;
oggi ogni lookup costa quanto il dizionario. Con la memoria indicizzata diventa
il candidato naturale, e con rapporti che l'RLE non può avvicinare su dati non
sintetici.

**Lettura da file nella VM.** Una primitiva che legge byte da un file
staccherebbe la dimensione del programma da quella del dato. Oggi le due cose
sono legate, e 269 byte diventano 12,6 MB di bytecode.

**Impacchettamento in bit dell'uscita.** Le lunghezze di corsa raramente
superano poche decine: cinque bit bastano quasi sempre. Vale la pena solo dopo
che il costo per accesso sia sceso.

**Conversione fra formati con `call` e `uncall`.** Un solo programma che
riconosce il tipo del file e sceglie la direzione: formato A in ingresso,
`call`; formato B, `uncall`; l'uscita è il file nell'altro formato. È il caso
in cui la reversibilità non è una verifica ma il meccanismo stesso: il
decodificatore non viene scritto, viene ottenuto.
