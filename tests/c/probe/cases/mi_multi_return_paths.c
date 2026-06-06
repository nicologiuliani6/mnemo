#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int classify(int x){if(x<0)return -1;if(x==0)return 0;return 1;}
int main(void){printf("%d %d %d\n",classify(-5),classify(0),classify(7));return 0;}
