#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=1;i<=20;i++){if(i%3==0)continue;if(i%5==0)continue;s+=i;}printf("%d\n",s);return 0;}
