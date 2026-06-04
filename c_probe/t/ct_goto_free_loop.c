#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int n=0;for(int i=2;i<30;i++){int prime=1;for(int j=2;j*j<=i;j++)if(i%j==0){prime=0;break;}if(prime)n++;}printf("%d\n",n);return 0;}
