#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int find(const char*s,char c){for(int i=0;s[i];i++)if(s[i]==c)return i;return -1;}
int main(void){printf("%d %d %d\n",find("hello",'l'),find("world",'z'),find("abc",'a'));return 0;}
