/* Mnemo fake stdio.h: solo printf (Mnemo lo handle nativamente). */
#ifndef _MNEMO_STDIO_H
#define _MNEMO_STDIO_H

int printf(const char *fmt, ...);

/* sprintf/snprintf: Mnemo compile-time, args devono essere costanti. */
int sprintf(char *buf, const char *fmt, ...);
int snprintf(char *buf, unsigned long n, const char *fmt, ...);

/* I/O stubs: VM no filesystem, Mnemo AST rewrite a 0. stdout/stderr
   sono puntatori opachi (non dereferenziabili) ma valid come arg
   sintattici. */
typedef struct __mn_FILE FILE;
extern FILE *stdout;
extern FILE *stderr;
extern FILE *stdin;

int fflush  (FILE *stream);
int setvbuf (FILE *stream, char *buf, int mode, unsigned long size);
void setbuf (FILE *stream, char *buf);
int feof    (FILE *stream);
int ferror  (FILE *stream);
void clearerr(FILE *stream);
int fileno  (FILE *stream);

/* fputs/fputc/fprintf: Mnemo AST rewrite a printf/putchar se stream==stdout,
   no-op se stream==stderr. */
int fputs   (const char *s, FILE *stream);
int fputc   (int c, FILE *stream);
int fprintf (FILE *stream, const char *fmt, ...);

#endif
