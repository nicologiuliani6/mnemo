#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct R{int key,val;};
int main(void){struct R a[5]={{3,30},{1,10},{4,40},{1,11},{5,50}};
for(int i=0;i<5;i++)for(int j=0;j<4-i;j++)if(a[j].key>a[j+1].key){struct R t=a[j];a[j]=a[j+1];a[j+1]=t;}
for(int i=0;i<5;i++)printf("%d:%d ",a[i].key,a[i].val);printf("\n");return 0;}
