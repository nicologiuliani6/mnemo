#include <stdio.h>

int main(void){int x=42;void*v=&x;int*p=(int*)v;printf("%d\n",*p);return 0;}
