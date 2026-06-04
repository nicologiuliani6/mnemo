#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sgn(int x){return x>0?1:x<0?-1:0;}
int main(void){for(int i=-2;i<=2;i++)printf("%d ",sgn(i));printf("\n");return 0;}
