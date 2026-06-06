#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int fact_acc(int n,int acc){return n<=1?acc:fact_acc(n-1,acc*n);}
int main(void){printf("%d %d\n",fact_acc(5,1),fact_acc(7,1));return 0;}
