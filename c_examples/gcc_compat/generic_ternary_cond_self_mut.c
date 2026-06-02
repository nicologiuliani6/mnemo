/* generic_ternary_cond_self_mut.c — la guardia di un ternario è mutata in un
 * ramo (`x = x ? 1 : (x=2, x+1)`). Regression del fix _lower_if_from_expr:
 * materializza la verità in un temp prima dei rami così la `fi` Kairos resta
 * stabile. Prima: fallimento silenzioso (exit 1, niente output). ev: x=3.
 */
#include "compat_runtime.h"

int main(void) {
  int x = 0;
  x = x ? 1 : (x = 2, x + 1);
  printf("%d\n", x);
  return x;
}
