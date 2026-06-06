#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=-3;i<=3;i++){int v=i<0?-i:i>0?i*2:100;s+=v;}printf("%d\n",s);return 0;}
