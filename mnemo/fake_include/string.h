/* Mnemo fake string.h: solo `strlen` / `strcmp` compile-time su
   stringa letterale o `char *p = "…";` con init costante. */
#ifndef _MNEMO_STRING_H
#define _MNEMO_STRING_H
#include <stddef.h>

size_t strlen(const char *s);
int strcmp(const char *a, const char *b);

#endif
