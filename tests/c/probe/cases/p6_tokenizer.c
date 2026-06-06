#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="  hello   world  foo ";int words=0,i=0;while(s[i]){while(s[i]==' ')i++;if(s[i]){words++;while(s[i]&&s[i]!=' ')i++;}}printf("%d\n",words);return 0;}
