#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s[50];for(int i=0;i<50;i++)s[i]=1;s[0]=s[1]=0;for(int i=2;i<50;i++)if(s[i])for(int j=2*i;j<50;j+=i)s[j]=0;int c=0;for(int i=0;i<50;i++)c+=s[i];printf("%d\n",c);return 0;}
