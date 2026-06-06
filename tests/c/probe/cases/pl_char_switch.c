#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="abcabc";int s1=0;for(int i=0;s[i];i++){switch(s[i]){case 'a':s1+=1;break;case 'b':s1+=10;break;case 'c':s1+=100;break;}}printf("%d\n",s1);return 0;}
