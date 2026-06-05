#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int modexp(int b,int e,int m){int r=1;b%=m;while(e>0){if(e&1)r=(r*b)%m;e>>=1;b=(b*b)%m;}return r;}
int main(void){printf("%d %d %d\n",modexp(3,5,7),modexp(2,10,1000),modexp(7,4,13));return 0;}
