#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int ipow(int b,int e){if(e==0)return 1;return b*ipow(b,e-1);}
int main(void){printf("%d %d %d\n",ipow(2,10),ipow(3,4),ipow(5,0));return 0;}
