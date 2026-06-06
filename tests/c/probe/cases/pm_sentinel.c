#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[8]={3,1,4,1,5,9,-1,2};int s=0;int*p=a;while(*p!=-1){s+=*p;p++;}printf("%d\n",s);return 0;}
