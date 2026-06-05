#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=12345,rev=0;do{rev=rev*10+n%10;n/=10;}while(n>0);printf("%d\n",rev);return 0;}
