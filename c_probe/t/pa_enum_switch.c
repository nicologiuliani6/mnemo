#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum Op{ADD,SUB,MUL,DIV};
int calc(enum Op o,int a,int b){switch(o){case ADD:return a+b;case SUB:return a-b;case MUL:return a*b;case DIV:return a/b;}return 0;}
int main(void){printf("%d %d %d %d\n",calc(ADD,6,3),calc(SUB,6,3),calc(MUL,6,3),calc(DIV,6,3));return 0;}
