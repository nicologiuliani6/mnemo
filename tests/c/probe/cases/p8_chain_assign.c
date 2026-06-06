#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a,b,c,d;a=b=c=d=7;a+=b+=c+=d+=1;printf("%d %d %d %d\n",a,b,c,d);return 0;}
