#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int gcd(int a,int b){return b==0?a:gcd(b,a%b);}
int main(void){printf("%d %d %d\n",gcd(48,36),gcd(17,5),gcd(100,80));return 0;}
