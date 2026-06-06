#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum Color{RED,GREEN=5,BLUE,YELLOW=10};
int main(void){enum Color c=GREEN;int s=RED+GREEN+BLUE+YELLOW;
printf("%d %d %d\n",c,s,BLUE-GREEN);return 0;}
