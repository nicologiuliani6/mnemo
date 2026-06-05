#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[6]={10,20,30,40,50,60};int*p=a+3;
printf("%d %d %d %ld\n",*p,p[-1],*(p+2),(long)(p-a));return 0;}
