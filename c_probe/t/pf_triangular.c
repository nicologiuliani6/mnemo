#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=1;i<=10;i++)for(int j=1;j<=i;j++)s+=i*j;printf("%d\n",s);return 0;}
