#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[2][3]={{1,2,3},{4,5,6}};int s=0;
for(int i=0;i<6;i++)s+=a[i<3?0:1][i%3];printf("%d\n",s);return 0;}
