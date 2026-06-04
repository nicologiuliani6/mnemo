#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a[5];int*p=&a[1];int*q=&a[3];printf("%d %d %d\n",p<q,p>q,p==q);return 0;}
