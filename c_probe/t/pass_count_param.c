#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void count(int n,int*out){*out=0;for(int i=1;i<=n;i++)*out+=i;}
int main(void){int r;count(10,&r);printf("%d\n",r);return 0;}
