#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void rev(char*s){int n=0;while(s[n])n++;for(int i=0,j=n-1;i<j;i++,j--){char t=s[i];s[i]=s[j];s[j]=t;}}
int main(void){char s[]="hello";rev(s);printf("%s\n",s);return 0;}
