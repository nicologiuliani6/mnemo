/*
 * compat_runtime.h
 * Dichiarazioni runtime condivise per test compilabili sia con Mnemo che con gcc.
 */
#ifndef GCC_COMPAT_RUNTIME_H
#define GCC_COMPAT_RUNTIME_H

#ifdef MNEMO
typedef unsigned int size_t;
int printf(const char *fmt, ...);
void *malloc(size_t n);
void free(void *p);
#else
#include <stdio.h>
#include <stdlib.h>
#endif

#endif /* GCC_COMPAT_RUNTIME_H */
