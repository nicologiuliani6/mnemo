/* generic_const_char_ptr.c — const char * e stringa letterale */
#include "compat_runtime.h"

int main(void) {
  const char *s = "ab";
  printf("%s\n", s);
  return 0;
}
