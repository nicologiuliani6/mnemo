#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void divmod(int a,int b,int*q,int*r){*q=a/b;*r=a%b;}
int main(void){int q,r;divmod(47,5,&q,&r);printf("%d %d\n",q,r);return 0;}
