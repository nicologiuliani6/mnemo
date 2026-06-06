#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void inc(int**p){(**p)++;}
int main(void){int x=10;int*q=&x;inc(&q);printf("%d\n",x);return 0;}
