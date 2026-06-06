#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[16];for(int i=0;i<16;i++)a[i]=i;int s=0;
for(int i=0;i<4;i++)for(int j=0;j<4;j++)s+=a[i*4+j]*((i+j)%2);printf("%d\n",s);return 0;}
