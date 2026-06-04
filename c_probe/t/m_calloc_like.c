#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int*a=malloc(sizeof(int)*5);for(int i=0;i<5;i++)a[i]=0;a[2]=7;int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
