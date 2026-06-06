#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10]={1,1,2,3,3,3,4,5,5,6};int w=0;for(int i=0;i<10;i++)if(i==0||a[i]!=a[i-1])a[w++]=a[i];for(int i=0;i<w;i++)printf("%d",a[i]);printf("\n");return 0;}
