#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="aaabbbcccd";char out[32];int o=0,i=0;while(s[i]){char c=s[i];int cnt=0;while(s[i]==c){cnt++;i++;}out[o++]=c;out[o++]='0'+cnt;}out[o]=0;printf("%s\n",out);return 0;}
