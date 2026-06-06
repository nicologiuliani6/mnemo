#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int keys[16],vals[16];for(int i=0;i<16;i++)keys[i]=-1;int ks[5]={3,17,8,3,25};for(int i=0;i<5;i++){int h=ks[i]%16;while(keys[h]!=-1&&keys[h]!=ks[i])h=(h+1)%16;keys[h]=ks[i];vals[h]++;}int found=0;for(int i=0;i<16;i++)if(keys[i]!=-1)found++;printf("%d\n",found);return 0;}
