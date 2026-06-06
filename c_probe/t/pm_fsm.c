#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*in="aabbbc";int state=0,acc=0;
for(int i=0;in[i];i++){char c=in[i];
if(state==0){if(c=='a')acc+=1;else state=1;}
if(state==1){if(c=='b')acc+=10;else state=2;}
if(state==2){acc+=100;}}printf("%d\n",acc);return 0;}
