/* generic_string_literal_index.c — indicizzazione di letterali stringa,
 * indice costante e runtime. */
#include "compat_runtime.h"
int main(void){
  int i; char b[8];
  for (i = 0; i < 5; i++) b[i] = "HELLO"[i];
  b[5] = 0;
  printf("%s %c %d\n", b, "WORLD"[1], "AB"[2]);   /* HELLO O 0 */
  return ("HELLO"[0]) & 0xFF;
}
