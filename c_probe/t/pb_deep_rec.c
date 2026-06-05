#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sumto(int n){if(n<=0)return 0;return n+sumto(n-1);}
int main(void){printf("%d %d\n",sumto(100),sumto(50));return 0;}
