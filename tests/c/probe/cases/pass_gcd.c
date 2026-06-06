#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int gcd(int a,int b){while(b){int t=b;b=a%b;a=t;}return a;}
int main(void){printf("%d %d\n",gcd(48,36),gcd(17,5));return 0;}
