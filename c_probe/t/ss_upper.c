#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){char s[]="Hello World";for(int i=0;s[i];i++)if(s[i]>='a'&&s[i]<='z')s[i]-=32;printf("%s\n",s);return 0;}
