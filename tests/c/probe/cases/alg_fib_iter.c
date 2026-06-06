#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){long long a=0,b=1;for(int i=0;i<40;i++){long long c=a+b;a=b;b=c;}printf("%lld\n",a);return 0;}
