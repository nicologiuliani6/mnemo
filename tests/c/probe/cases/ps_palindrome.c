#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int pal(const char*s){int n=0;while(s[n])n++;for(int i=0,j=n-1;i<j;i++,j--)if(s[i]!=s[j])return 0;return 1;}
int main(void){printf("%d %d %d\n",pal("racecar"),pal("hello"),pal("abba"));return 0;}
