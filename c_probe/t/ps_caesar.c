#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char s[]="HELLO";int sh=3;for(int i=0;s[i];i++)if(s[i]>='A'&&s[i]<='Z')s[i]='A'+(s[i]-'A'+sh)%26;printf("%s\n",s);return 0;}
