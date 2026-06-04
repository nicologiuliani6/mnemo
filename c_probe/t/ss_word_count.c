#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){const char*s="the quick brown fox";int words=0,in=0;for(int i=0;s[i];i++){if(s[i]!=' '){if(!in){words++;in=1;}}else in=0;}printf("%d\n",words);return 0;}
