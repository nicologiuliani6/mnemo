#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[5]={1,2,3,4,5};a[2]+=a[0];a[2]*=a[1];a[2]-=a[3];a[2]<<=1;
int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d %d\n",a[2],s);return 0;}
