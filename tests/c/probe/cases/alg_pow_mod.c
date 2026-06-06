#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

long long pm(long long b,long long e,long long m){long long r=1;b%=m;while(e>0){if(e&1)r=r*b%m;e>>=1;b=b*b%m;}return r;}
int main(void){printf("%lld\n",pm(7,256,13));return 0;}
