#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[5]={10,20,30,40,50};int s=0;for(int i=0;i<5;i++)s+=a[i<2?0:i<4?2:4];printf("%d\n",s);return 0;}
