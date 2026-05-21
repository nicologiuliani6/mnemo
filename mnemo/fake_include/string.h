/* Mnemo fake string.h:
   - `strlen` / `strcmp` compile-time su stringa letterale o
     `char *p = "…";` con init costante.
   - `memcpy(dst, src, n)` / `memset(dst, v, n)` espansi per-slot
     se dst (e src) sono array Mnemo e `n` è una costante. */
#ifndef _MNEMO_STRING_H
#define _MNEMO_STRING_H
#include <stddef.h>

size_t strlen(const char *s);
int strcmp(const char *a, const char *b);
void *memcpy(void *dst, const void *src, size_t n);
void *memset(void *dst, int v, size_t n);

#endif
