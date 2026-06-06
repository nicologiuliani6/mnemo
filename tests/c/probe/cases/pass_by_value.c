#include <stdio.h>

void f(int x){x=99;}
int main(void){int a=1;f(a);printf("%d\n",a);return 0;}
