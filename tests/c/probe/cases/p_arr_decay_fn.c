#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int first(int*p){return *p;}
int main(void){int a[3]={9,8,7};printf("%d\n",first(a));printf("%d\n",first(a+1));return 0;}
