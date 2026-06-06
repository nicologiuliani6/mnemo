#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void setv(int*out){int*p=malloc(sizeof(int));p[0]=99;*out=p[0];free(p);}
int main(void){int r=0;setv(&r);printf("%d\n",r);return 0;}
