#include <stdio.h>

int sidef(int*c){(*c)++;return 1;}
int main(void){int calls=0;int r=(0&&sidef(&calls))||(1||sidef(&calls));printf("%d %d\n",r,calls);return 0;}
