#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10]={[0]=1,[9]=10,[5]=5,[3]=3};int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d\n",s);return 0;}
