#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned seed=12345;int counts[6]={0};for(int i=0;i<60;i++){seed=seed*1103515245u+12345u;int r=(seed>>16)%6;counts[r]++;}int t=0;for(int i=0;i<6;i++)t+=counts[i];printf("%d\n",t);return 0;}
