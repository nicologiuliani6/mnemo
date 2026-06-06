#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const int lut[5]={2,3,5,7,11};int s=0;for(int i=0;i<5;i++)s+=lut[i]*i;printf("%d\n",s);return 0;}
