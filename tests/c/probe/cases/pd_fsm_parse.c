#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="-42";int sign=1,i=0,val=0;
if(s[i]=='-'){sign=-1;i++;}else if(s[i]=='+')i++;
while(s[i]>='0'&&s[i]<='9'){val=val*10+(s[i]-'0');i++;}
printf("%d\n",sign*val);return 0;}
