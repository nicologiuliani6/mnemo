/* Mnemo fake stddef.h
   Word-size integer types (la VM Kairos opera solo su `int`). */
#ifndef _MNEMO_STDDEF_H
#define _MNEMO_STDDEF_H

typedef int size_t;
typedef int ssize_t;
typedef int ptrdiff_t;
typedef int wchar_t;

#ifndef NULL
#define NULL ((void *)0)
#endif

#endif
