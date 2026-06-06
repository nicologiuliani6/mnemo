#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=0;i<5;i++){switch(i){case 0:s+=1;case 1:s+=2;break;case 2:s+=4;default:s+=8;}}printf("%d\n",s);return 0;}
