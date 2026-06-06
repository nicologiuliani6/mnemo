#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[8]={0,1,2,3,4,5,6,7};int*p=&a[2];int*q=&a[6];
printf("%d %d %d\n",(int)(q-p),*p,*q);return 0;}
