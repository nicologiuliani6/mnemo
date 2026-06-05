#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[5]={1,2,3,4,5};int*p=a;int*end=a+5;int s=0;while(p!=end)s+=*p++;
printf("%d %d\n",s,(int)(end-a));return 0;}
