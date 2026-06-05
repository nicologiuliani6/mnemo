#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i;int*p=&a[2];int*q=&a[7];
printf("%ld %d\n",(long)(q-p),(int)(p<q));return 0;}
