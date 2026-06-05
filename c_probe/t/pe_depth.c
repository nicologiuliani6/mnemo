#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int depth(int n,int d){if(n<=1)return d;if(n%2==0)return depth(n/2,d+1);return depth(3*n+1,d+1);}
int main(void){printf("%d %d %d\n",depth(27,0),depth(7,0),depth(1,0));return 0;}
