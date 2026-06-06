#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int st=0,out=0;const char*cmds="++--+";for(int i=0;cmds[i];i++){switch(cmds[i]){case '+':out+=st<2?5:1;st++;break;case '-':out-=1;st--;break;}}printf("%d %d\n",out,st);return 0;}
