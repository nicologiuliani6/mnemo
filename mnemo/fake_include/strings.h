/* Mnemo fake strings.h: POSIX legacy. Mnemo lower bzero/bcopy/strcasecmp/
   strncasecmp/index/rindex come AST rewrite o compile-time. */
#ifndef _MNEMO_STRINGS_H
#define _MNEMO_STRINGS_H

#include <stddef.h>

int  strcasecmp (const char *a, const char *b);
int  strncasecmp(const char *a, const char *b, size_t n);
void bzero      (void *p, size_t n);
void bcopy      (const void *src, void *dst, size_t n);
char *index     (const char *s, int c);
char *rindex    (const char *s, int c);

#endif
