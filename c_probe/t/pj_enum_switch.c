#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum Color{RED,GREEN,BLUE};
int val(enum Color c){switch(c){case RED:return 100;case GREEN:return 200;case BLUE:return 300;}return 0;}
int main(void){int s=0;for(int i=0;i<3;i++)s+=val(i);printf("%d\n",s);return 0;}
