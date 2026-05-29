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

/* atoi/atol/atoll: Mnemo compile-time su string literal. */
int             atoi (const char *s);
long            atol (const char *s);
long long       atoll(const char *s);

/* div/ldiv/lldiv: Mnemo AST rewrite a compound literal `(T){a/b, a%b}`. */
typedef struct { int       quot; int       rem; } div_t;
typedef struct { long      quot; long      rem; } ldiv_t;
typedef struct { long long quot; long long rem; } lldiv_t;

div_t   div  (int       n, int       d);
ldiv_t  ldiv (long      n, long      d);
lldiv_t lldiv(long long n, long long d);

#endif
