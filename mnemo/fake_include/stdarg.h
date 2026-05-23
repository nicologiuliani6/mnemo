#ifndef _MNEMO_STDARG_H
#define _MNEMO_STDARG_H

/* Mnemo: va_list = int (indice nei cell variadici __mn_vaN).
   va_start(ap, last) azzera l'indice. va_arg legge __mn_va<ap> e avanza ap.
   va_end no-op. MAX_VA hardcoded = 8 lato compilatore. */

typedef int va_list;

extern int __mn_va_arg(int idx);

#define va_start(ap, last) ((ap) = 0)
#define va_arg(ap, T)      (__mn_va_arg((ap)++))
#define va_end(ap)         ((void)0)
#define va_copy(d, s)      ((d) = (s))

#endif
