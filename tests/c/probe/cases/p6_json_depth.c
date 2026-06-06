#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="{[{}],[[]]}";int d=0,mx=0;for(int i=0;s[i];i++){if(s[i]=='{'||s[i]=='[')d++;else if(s[i]=='}'||s[i]==']')d--;if(d>mx)mx=d;}printf("%d\n",mx);return 0;}
