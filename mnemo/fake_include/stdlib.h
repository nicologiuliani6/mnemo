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

/* strtol/strtoul/strtoll/strtoull: Mnemo compile-time su string literal,
   endptr deve essere NULL, base const. */
long              strtol  (const char *s, char **endptr, int base);
unsigned long     strtoul (const char *s, char **endptr, int base);
long long         strtoll (const char *s, char **endptr, int base);
unsigned long long strtoull(const char *s, char **endptr, int base);

/* div/ldiv/lldiv: Mnemo AST rewrite a compound literal `(T){a/b, a%b}`. */
typedef struct { int       quot; int       rem; } div_t;
typedef struct { long      quot; long      rem; } ldiv_t;
typedef struct { long long quot; long long rem; } lldiv_t;

div_t   div  (int       n, int       d);
ldiv_t  ldiv (long      n, long      d);
lldiv_t lldiv(long long n, long long d);

/* exit/abort: Mnemo AST rewrite a `return N` (solo dentro main).
   abort() → return 134 (= 128 + SIGABRT). */
void exit (int status);
void abort(void);

/* getenv: VM no env, Mnemo AST rewrite a NULL. */
char *getenv(const char *name);

#endif
