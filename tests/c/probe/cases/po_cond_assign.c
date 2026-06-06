#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[5]={5,0,3,0,8};int last=0,s=0;for(int i=0;i<5;i++){if(a[i])last=a[i];s+=last;}printf("%d %d\n",s,last);return 0;}
