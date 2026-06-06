#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Inner{int v;};struct Outer{struct Inner in;int tag;};
int main(void){struct Outer arr[3];for(int i=0;i<3;i++){arr[i].in.v=i*10;arr[i].tag=i;}
int s=0;for(int i=0;i<3;i++)s+=arr[i].in.v+arr[i].tag;printf("%d\n",s);return 0;}
