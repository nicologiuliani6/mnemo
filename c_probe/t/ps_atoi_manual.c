#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int ai(const char*s){int r=0,sg=1;if(*s=='-'){sg=-1;s++;}while(*s>='0'&&*s<='9'){r=r*10+(*s-'0');s++;}return r*sg;}
int main(void){printf("%d %d %d\n",ai("12345"),ai("-678"),ai("0"));return 0;}
