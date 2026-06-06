#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int counter=0;
void bump(int*p,int by){*p+=by;}
int main(void){bump(&counter,5);bump(&counter,3);int*q=&counter;*q+=2;printf("%d\n",counter);return 0;}
