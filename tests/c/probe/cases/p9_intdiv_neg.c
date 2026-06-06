#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int vals[4]={-17,17,-17,17},divs[4]={5,-5,-5,5};
for(int i=0;i<4;i++)printf("%d %d\n",vals[i]/divs[i],vals[i]%divs[i]);return 0;}
