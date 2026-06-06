#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sumto(int n,int acc){if(n==0)return acc;return sumto(n-1,acc+n);}
int main(void){printf("%d\n",sumto(100,0));return 0;}
