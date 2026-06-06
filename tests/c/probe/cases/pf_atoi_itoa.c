#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int my_atoi(const char*s){int v=0,sign=1,i=0;if(s[0]=='-'){sign=-1;i=1;}while(s[i]){v=v*10+(s[i]-'0');i++;}return sign*v;}
int main(void){printf("%d %d\n",my_atoi("12345"),my_atoi("-678"));return 0;}
