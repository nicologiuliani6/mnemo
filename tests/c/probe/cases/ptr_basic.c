#include <stdio.h>

int main(void){int x=5;int*p=&x;*p=9;printf("%d %d\n",x,*p);return 0;}
