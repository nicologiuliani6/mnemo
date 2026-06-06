#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const int sq[8]={0,1,4,9,16,25,36,49};int s=0;for(int i=0;i<8;i++)s+=sq[i];printf("%d\n",s);return 0;}
