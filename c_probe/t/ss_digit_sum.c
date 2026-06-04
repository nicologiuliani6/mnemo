#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){const char*s="a1b2c3d4";int sum=0;for(int i=0;s[i];i++)if(s[i]>='0'&&s[i]<='9')sum+=s[i]-'0';printf("%d\n",sum);return 0;}
