#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Item{int id,qty;};
int main(void){int n=5;struct Item*items=malloc(sizeof(struct Item)*n);
for(int i=0;i<n;i++){items[i].id=i;items[i].qty=(i+1)*10;}
int s=0;for(int i=0;i<n;i++)s+=items[i].id*items[i].qty;printf("%d\n",s);free(items);return 0;}
