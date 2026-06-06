#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int moves=0;
void h(int n,int f,int t,int v){if(n==0)return;h(n-1,f,v,t);moves++;h(n-1,v,t,f);}
int main(void){h(4,0,2,1);printf("%d\n",moves);return 0;}
