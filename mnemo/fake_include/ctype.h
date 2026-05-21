#ifndef _MNEMO_CTYPE_H
#define _MNEMO_CTYPE_H

/* Macro a singola valutazione: in Mnemo non c'è libc, quindi
   `<ctype.h>` è implementato come confronti ASCII inline. */

#define isdigit(c)  ((c) >= '0' && (c) <= '9')
#define isupper(c)  ((c) >= 'A' && (c) <= 'Z')
#define islower(c)  ((c) >= 'a' && (c) <= 'z')
#define isalpha(c)  (isupper(c) || islower(c))
#define isalnum(c)  (isalpha(c) || isdigit(c))
#define isspace(c)  ((c) == ' ' || (c) == '\t' || (c) == '\n' || (c) == '\r' || (c) == '\v' || (c) == '\f')
#define isxdigit(c) (isdigit(c) || ((c) >= 'a' && (c) <= 'f') || ((c) >= 'A' && (c) <= 'F'))
#define ispunct(c)  (((c) >= '!' && (c) <= '/') || ((c) >= ':' && (c) <= '@') || ((c) >= '[' && (c) <= '`') || ((c) >= '{' && (c) <= '~'))
#define iscntrl(c)  (((c) >= 0 && (c) <= 31) || (c) == 127)
#define isprint(c)  ((c) >= ' ' && (c) <= '~')
#define isgraph(c)  ((c) > ' ' && (c) <= '~')

#define toupper(c)  (islower(c) ? (c) - 'a' + 'A' : (c))
#define tolower(c)  (isupper(c) ? (c) - 'A' + 'a' : (c))

#endif
