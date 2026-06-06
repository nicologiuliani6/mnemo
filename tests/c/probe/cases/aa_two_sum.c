#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[6]={2,7,11,15,3,6},tgt=9;int r=-1;for(int i=0;i<6&&r<0;i++)for(int j=i+1;j<6;j++)if(a[i]+a[j]==tgt){r=i*10+j;break;}printf("%d\n",r);return 0;}
