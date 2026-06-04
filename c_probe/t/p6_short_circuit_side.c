#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int calls=0;int inc(void){calls++;return 1;}
int main(void){int r1=0||inc();int r2=1&&inc();int r3=0&&inc();int r4=1||inc();printf("%d %d %d %d %d\n",r1,r2,r3,r4,calls);return 0;}
