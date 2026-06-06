#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=0,b=1;for(int i=0;i<15;i++){int t=a+b;a=b;b=t;}printf("%d %d\n",a,b);return 0;}
