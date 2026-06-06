#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="a,bb,ccc,d";int parts=1;for(int i=0;s[i];i++)if(s[i]==',')parts++;printf("%d\n",parts);return 0;}
