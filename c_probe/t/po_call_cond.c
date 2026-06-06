#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int more(int i){return i<10;}
int main(void){int s=0;for(int i=0;more(i);i++)s+=i;printf("%d\n",s);return 0;}
