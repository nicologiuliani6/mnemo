#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int weekday(int d){switch(d){case 0:return 7;case 6:return 6;}return d;}
int main(void){int s=0;for(int i=0;i<7;i++)s=s*10+weekday(i);printf("%d\n",s);return 0;}
