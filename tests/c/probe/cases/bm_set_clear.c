#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned f=0;f|=(1<<3);f|=(1<<7);f&=~(1<<3);printf("%u %d\n",f,(f>>7)&1);return 0;}
