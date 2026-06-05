#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sum_until(const int*p,int sentinel){int s=0;while(*p!=sentinel){s+=*p;p++;}return s;}
int main(void){int a[6]={5,10,15,-1,99,99};printf("%d\n",sum_until(a,-1));return 0;}
