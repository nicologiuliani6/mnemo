// SKIP: fn-ptr come parametro (dispatch cross-call-site) non supportato
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int apply(int(*f)(int),int x){return f(x);}
int sq(int x){return x*x;}
int main(void){printf("%d\n",apply(sq,7));return 0;}
