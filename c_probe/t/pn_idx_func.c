#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int idx(int i){return (i*7)%10;}
int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i*i;int s=0;for(int i=0;i<10;i++)s+=a[idx(i)];printf("%d\n",s);return 0;}
