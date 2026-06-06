#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10];int n=sizeof(a)/sizeof(a[0]);int b=sizeof(int)*2;printf("%d %d\n",n,b);return 0;}
