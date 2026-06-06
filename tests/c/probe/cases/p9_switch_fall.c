#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int r=0;for(int x=0;x<5;x++){switch(x){case 0:case 1:r+=1;break;case 2:r+=10;case 3:r+=100;break;default:r+=1000;}}printf("%d\n",r);return 0;}
