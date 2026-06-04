#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int x=5,y=9;int*const p=&x;*p=10;printf("%d\n",x);const int*q=&y;printf("%d\n",*q);return 0;}
