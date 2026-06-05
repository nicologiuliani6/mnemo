#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int pairs[6][2]={{-7,2},{7,-2},{-7,-2},{-1,3},{1,-3},{-8,3}};
for(int i=0;i<6;i++)printf("%d %d\n",pairs[i][0]/pairs[i][1],pairs[i][0]%pairs[i][1]);return 0;}
