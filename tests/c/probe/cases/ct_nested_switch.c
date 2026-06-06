#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int r=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++){switch(i){case 0:r+=j;break;case 1:r+=j*2;break;default:r+=j*3;}}printf("%d\n",r);return 0;}
