#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char s[]="Hello World 123";int up=0,lo=0,dg=0,sp=0;
for(char*p=s;*p;p++){if(*p>='A'&&*p<='Z')up++;else if(*p>='a'&&*p<='z')lo++;
else if(*p>='0'&&*p<='9')dg++;else sp++;}
printf("%d %d %d %d\n",up,lo,dg,sp);return 0;}
