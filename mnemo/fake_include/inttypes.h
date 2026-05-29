/* Mnemo fake inttypes.h: macro PRI/SCN per stampa formattata di int*_t.
   Mnemo treat tutti i tipi int*_t come int (cell uniforme), quindi i
   PRI macros si riducono a "d"/"u"/"x" senza prefix di taglia. */
#ifndef _MNEMO_INTTYPES_H
#define _MNEMO_INTTYPES_H

#include <stdint.h>

#define PRId8   "d"
#define PRId16  "d"
#define PRId32  "d"
#define PRId64  "lld"
#define PRIdMAX "lld"
#define PRIdPTR "d"

#define PRIi8   "d"
#define PRIi16  "d"
#define PRIi32  "d"
#define PRIi64  "lld"
#define PRIiMAX "lld"
#define PRIiPTR "d"

#define PRIu8   "u"
#define PRIu16  "u"
#define PRIu32  "u"
#define PRIu64  "llu"
#define PRIuMAX "llu"
#define PRIuPTR "u"

#define PRIx8   "x"
#define PRIx16  "x"
#define PRIx32  "x"
#define PRIx64  "llx"
#define PRIxMAX "llx"
#define PRIxPTR "x"

#define PRIX8   "X"
#define PRIX16  "X"
#define PRIX32  "X"
#define PRIX64  "llX"
#define PRIXMAX "llX"
#define PRIXPTR "X"

#define PRIo8   "o"
#define PRIo16  "o"
#define PRIo32  "o"
#define PRIo64  "llo"
#define PRIoMAX "llo"
#define PRIoPTR "o"

#endif
