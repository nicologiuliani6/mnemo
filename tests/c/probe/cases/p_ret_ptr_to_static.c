#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int*getbuf(void){static int b[3]={11,22,33};return b;}
int main(void){int*p=getbuf();printf("%d %d %d\n",p[0],p[1],p[2]);return 0;}
