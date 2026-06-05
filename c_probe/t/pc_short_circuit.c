#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int calls=0;int chk(int x){calls++;return x>0;}
int main(void){int a=chk(1)&&chk(2)&&chk(-1)&&chk(3);int b=chk(-1)||chk(0)||chk(5);
printf("%d %d %d\n",a,b,calls);return 0;}
