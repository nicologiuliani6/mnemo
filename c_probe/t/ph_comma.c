#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=0,j=10;i<j;i++,j--)s+=i*j;printf("%d\n",s);return 0;}
