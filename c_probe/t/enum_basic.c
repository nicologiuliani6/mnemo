#include <stdio.h>

enum Color{RED,GREEN=5,BLUE};
int main(void){printf("%d %d %d\n",RED,GREEN,BLUE);return 0;}
