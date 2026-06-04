#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int total=0;for(int i=1;i<=5;i++)for(int j=1;j<=5;j++)total+=i*j;printf("%d\n",total);return 0;}
