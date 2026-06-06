#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int*a=malloc(sizeof(int)*3);int*b=malloc(sizeof(int)*3);for(int i=0;i<3;i++){a[i]=i;b[i]=i*10;}printf("%d %d\n",a[2],b[2]);free(a);free(b);return 0;}
