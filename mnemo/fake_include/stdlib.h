/* Mnemo fake stdlib.h
   Solo malloc/free dichiarazioni (Mnemo li lowera via ptr_pool). */
#ifndef _MNEMO_STDLIB_H
#define _MNEMO_STDLIB_H

#include <stddef.h>

void *malloc(size_t n);
void  free(void *p);

#endif
