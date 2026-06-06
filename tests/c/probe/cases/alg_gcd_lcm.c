#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int gcd(int a,int b){return b?gcd(b,a%b):a;}
int main(void){int a=12,b=18;printf("%d %d\n",gcd(a,b),a/gcd(a,b)*b);return 0;}
