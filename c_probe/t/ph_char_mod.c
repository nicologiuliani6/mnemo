#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char s[10];for(int i=0;i<9;i++)s[i]='a'+i;s[9]=0;
for(int i=0;i<9;i++)if(s[i]%2==0)s[i]-=32;printf("%s\n",s);return 0;}
