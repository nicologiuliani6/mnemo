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

/* `offsetof(T, M)`: Mnemo C-subset → field-index * _SIZEOF_SCALAR.
   gcc espande il proprio offsetof in __builtin_offsetof; usiamo lo stesso
   token così c_parse.py può riscriverlo in `__mn_offsetof_str("T","M")`. */
#ifndef offsetof
#define offsetof(T, M) __builtin_offsetof(T, M)
#endif

#endif
