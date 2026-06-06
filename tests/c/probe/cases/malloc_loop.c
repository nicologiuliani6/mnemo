#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int s=0;for(int i=0;i<5;i++){int*p=malloc(sizeof(int));*p=i*i;s+=*p;free(p);}printf("%d\n",s);return 0;}
