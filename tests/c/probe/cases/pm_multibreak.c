#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int found=0,fi=0,fj=0;int m[5][5];for(int i=0;i<5;i++)for(int j=0;j<5;j++)m[i][j]=i*5+j;
for(int i=0;i<5&&!found;i++)for(int j=0;j<5;j++){if(m[i][j]==13){found=1;fi=i;fj=j;break;}}
printf("%d %d %d\n",found,fi,fj);return 0;}
