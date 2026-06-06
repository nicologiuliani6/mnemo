#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int cnt=0;int f(int x){cnt++;return x;}
int main(void){int a=f(0)&&f(1);int b=f(1)||f(0);printf("%d %d %d\n",a,b,cnt);return 0;}
