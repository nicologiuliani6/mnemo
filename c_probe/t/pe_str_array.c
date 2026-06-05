#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*days[3]={"Mon","Tue","Wed"};int s=0;
for(int i=0;i<3;i++)for(int j=0;days[i][j];j++)s+=days[i][j];printf("%d\n",s);return 0;}
