#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int mycmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a-*b;}
int main(void){printf("%d %d %d\n",mycmp("abc","abc")==0,mycmp("abc","abd")<0,mycmp("abd","abc")>0);return 0;}
