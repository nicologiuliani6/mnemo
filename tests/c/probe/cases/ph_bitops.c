#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int pc(unsigned v){int c=0;while(v){c+=v&1;v>>=1;}return c;}
int main(void){unsigned x=0;x|=(1<<3);x|=(1<<5);x&=~(1<<3);x^=(1<<7);
printf("%u %d\n",x,pc(x));return 0;}
