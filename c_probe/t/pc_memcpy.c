#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int src[5]={10,20,30,40,50},dst[5];
for(int i=0;i<5;i++)dst[i]=src[i];int s=0;for(int i=0;i<5;i++)s+=dst[i];printf("%d\n",s);return 0;}
