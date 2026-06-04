#include <stdio.h>

typedef struct{int x;int y;}Pt;
int main(void){Pt p={3,4};printf("%d\n",p.x*p.y);return 0;}
