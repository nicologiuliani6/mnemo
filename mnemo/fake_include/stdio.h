/* Mnemo fake stdio.h: solo printf (Mnemo lo handle nativamente). */
#ifndef _MNEMO_STDIO_H
#define _MNEMO_STDIO_H

int printf(const char *fmt, ...);

/* sprintf/snprintf: Mnemo compile-time, args devono essere costanti. */
int sprintf(char *buf, const char *fmt, ...);
int snprintf(char *buf, unsigned long n, const char *fmt, ...);

#endif
