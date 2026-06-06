#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int slen(const char*s){int n=0;while(s[n])n++;return n;}
int scmp(const char*a,const char*b){int i=0;while(a[i]&&a[i]==b[i])i++;return a[i]-b[i];}
int main(void){printf("%d %d %d\n",slen("hello"),scmp("abc","abc"),scmp("abd","abc"));return 0;}
