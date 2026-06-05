#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=1,b=2,c=3;int*pa[3]={&a,&b,&c};int s=0;for(int i=0;i<3;i++)s+=*pa[i];
*pa[1]=20;s+=b;printf("%d\n",s);return 0;}
