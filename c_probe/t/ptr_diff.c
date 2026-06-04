#include <stdio.h>

int main(void){int a[10];int*p=&a[2];int*q=&a[7];printf("%ld\n",(long)(q-p));return 0;}
