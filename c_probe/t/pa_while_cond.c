#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=1000,steps=0;while(x>1&&steps<100){if(x%2==0)x/=2;else x=3*x+1;steps++;}printf("%d %d\n",x,steps);return 0;}
