#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int next(void){static int s=1;s=s*2+1;return s;}
int main(void){for(int i=0;i<6;i++)printf("%d ",next());printf("\n");return 0;}
