#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int i=5;int a=i++ + ++i;int j=10;int b=j-- - --j;printf("%d %d %d %d\n",a,i,b,j);return 0;}
