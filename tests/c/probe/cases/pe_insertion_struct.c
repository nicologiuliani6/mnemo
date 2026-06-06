#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct R{int k;};
int main(void){struct R a[6]={{5},{2},{8},{1},{9},{3}};
for(int i=1;i<6;i++){struct R key=a[i];int j=i-1;while(j>=0&&a[j].k>key.k){a[j+1]=a[j];j--;}a[j+1]=key;}
for(int i=0;i<6;i++)printf("%d",a[i].k);printf("\n");return 0;}
