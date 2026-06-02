/* generic_char_wrap.c — aritmetica char/unsigned char wrappa a 8 bit. */
#include "compat_runtime.h"
int main(void){
  unsigned char a = 250; a += 10;        /* 4 */
  unsigned char b = 200; b = b + 100;    /* 44 */
  signed char s = 120; s += 10;          /* -126 */
  char c = 65; c++;                      /* 'B' = 66 */
  unsigned char d = 5; d--;              /* 4 */
  printf("%d %d %d %d %d\n", a, b, s, c, d);
  return (a + b) & 0xFF;
}
