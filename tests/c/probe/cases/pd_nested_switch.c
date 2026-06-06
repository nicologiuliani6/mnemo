#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int r=0;for(int a=0;a<3;a++)for(int b=0;b<3;b++){switch(a){case 0:switch(b){case 0:r+=1;break;default:r+=2;}break;case 1:r+=10;break;default:r+=100;}}printf("%d\n",r);return 0;}
