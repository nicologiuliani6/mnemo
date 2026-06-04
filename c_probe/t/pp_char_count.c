#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int countc(const char*s,char c){int n=0;while(*s)if(*s++==c)n++;return n;}
int main(void){printf("%d\n",countc("mississippi",'s'));return 0;}
