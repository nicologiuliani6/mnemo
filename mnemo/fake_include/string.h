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
int strncmp(const char *a, const char *b, size_t n);
int memcmp(const void *a, const void *b, size_t n);
size_t strspn(const char *s, const char *accept);
size_t strcspn(const char *s, const char *reject);
char *strchr(const char *s, int c);
char *strrchr(const char *s, int c);
char *strstr(const char *haystack, const char *needle);
char *strpbrk(const char *s, const char *accept);
char *strdup(const char *s);
void *memcpy(void *dst, const void *src, size_t n);
void *memset(void *dst, int v, size_t n);
char *strcpy(char *dst, const char *src);
char *strncpy(char *dst, const char *src, size_t n);
void *memmove(void *dst, const void *src, size_t n);

#endif
