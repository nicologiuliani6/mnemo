#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void it(int x,char*b){int i=0,neg=0;if(x<0){neg=1;x=-x;}char t[16];int j=0;if(x==0)t[j++]='0';while(x){t[j++]='0'+x%10;x/=10;}if(neg)b[i++]='-';while(j)b[i++]=t[--j];b[i]=0;}
int main(void){char b[16];it(-4231,b);printf("%s\n",b);it(0,b);printf("%s\n",b);return 0;}
