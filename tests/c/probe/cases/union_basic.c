#include <stdio.h>

union U{int i;char c;};
int main(void){union U u;u.i=65;printf("%d\n",u.i);u.c='A';printf("%d\n",u.c);return 0;}
