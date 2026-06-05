#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10]={0};for(int i=0;i<20;i++)a[i%10]+=i;int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d %d\n",a[0],s);return 0;}
