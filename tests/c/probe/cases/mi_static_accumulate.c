// SKIP: arg-eval-order unspecified (gcc R-to-L vs mnemo L-to-R w/ side effects)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int acc(int x){static int total=0;total+=x;return total;}
int main(void){printf("%d %d %d %d\n",acc(1),acc(2),acc(3),acc(4));return 0;}
