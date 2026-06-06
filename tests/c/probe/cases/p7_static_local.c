#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int counter(void){static int c=0;c++;return c;}
int main(void){int s=0;for(int i=0;i<5;i++)s+=counter();printf("%d\n",s);return 0;}
