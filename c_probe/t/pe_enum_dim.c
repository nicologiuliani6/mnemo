#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum{N=5};
int main(void){int a[N];for(int i=0;i<N;i++)a[i]=i*i;int s=0;for(enum{} ;0;);for(int i=0;i<N;i++)s+=a[i];printf("%d\n",s);return 0;}
