#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char s[]="HELLO";for(int i=0;s[i];i++)s[i]=(s[i]-'A'+3)%26+'A';printf("%s\n",s);return 0;}
