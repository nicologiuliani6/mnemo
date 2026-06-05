#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char s[]="abcABC123";int la=0,ua=0,di=0;for(char*p=s;*p;++p){if(*p>='a'&&*p<='z')la++;else if(*p>='A'&&*p<='Z')ua++;else di++;}printf("%d %d %d\n",la,ua,di);return 0;}
