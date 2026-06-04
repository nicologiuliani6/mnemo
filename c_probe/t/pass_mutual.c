#include <stdio.h>

int iseven(int n);int isodd(int n){return n==0?0:iseven(n-1);}
int iseven(int n){return n==0?1:isodd(n-1);}
int main(void){printf("%d %d\n",iseven(10),isodd(7));return 0;}
