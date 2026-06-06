#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum Op{ADD,SUB,MUL};
int apply(enum Op o,int a,int b){switch(o){case ADD:return a+b;case SUB:return a-b;case MUL:return a*b;}return 0;}
int main(void){printf("%d %d %d\n",apply(ADD,6,3),apply(SUB,6,3),apply(MUL,6,3));return 0;}
