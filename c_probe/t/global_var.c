#include <stdio.h>

int g=10;
void inc(void){g+=5;}
int main(void){inc();inc();printf("%d\n",g);return 0;}
