/* Mnemo fake stdlib.h
   Solo malloc/free dichiarazioni (Mnemo li lowera via ptr_pool). */
#ifndef _MNEMO_STDLIB_H
#define _MNEMO_STDLIB_H

#include <stddef.h>

void *malloc(size_t n);
void  free(void *p);

/* abs / labs / llabs: Mnemo lower built-in. */
int             abs(int x);
long            labs(long x);
long long       llabs(long long x);

/* atoi: Mnemo compile-time su string literal. */
int             atoi(const char *s);

#endif
