#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[20];for(int i=0;i<20;i++)a[i]=i;int s=0;
for(int i=0;i<5;i++)s+=a[i*4]+a[i*4+1];printf("%d\n",s);return 0;}
