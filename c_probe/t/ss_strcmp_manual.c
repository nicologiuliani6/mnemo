#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int cmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a-*b;}
int main(void){printf("%d %d %d\n",cmp("abc","abc")==0,cmp("abc","abd")<0,cmp("abd","abc")>0);return 0;}
