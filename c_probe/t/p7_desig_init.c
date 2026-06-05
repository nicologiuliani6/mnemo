#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[8]={[2]=20,[5]=50,[0]=1};int s=0;for(int i=0;i<8;i++)s+=a[i];printf("%d\n",s);return 0;}
