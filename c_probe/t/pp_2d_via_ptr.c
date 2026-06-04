#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int m[3][3];int*base=&m[0][0];for(int i=0;i<9;i++)base[i]=i*i;printf("%d %d\n",m[1][1],m[2][2]);return 0;}
