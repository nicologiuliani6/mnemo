#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int gcd(int a,int b){while(a!=b){if(a>b)a-=b;else b-=a;}return a;}
int main(void){printf("%d %d %d\n",gcd(48,36),gcd(17,5),gcd(100,75));return 0;}
