#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=3;int*a=malloc(sizeof(int)*n);int*b=malloc(sizeof(int)*n);
for(int i=0;i<n;i++){a[i]=i+1;b[i]=(i+1)*10;}int*p=a;int s=0;
for(int k=0;k<2;k++){for(int i=0;i<n;i++)s+=p[i];p=b;}printf("%d\n",s);free(a);free(b);return 0;}
