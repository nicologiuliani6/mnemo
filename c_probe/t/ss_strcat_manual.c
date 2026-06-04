#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){char buf[20]="abc";int n=0;while(buf[n])n++;char*add="def";int i=0;while(add[i])buf[n++]=add[i++];buf[n]=0;printf("%s\n",buf);return 0;}
