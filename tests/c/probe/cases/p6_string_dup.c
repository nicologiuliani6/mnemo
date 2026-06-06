// SKIP: printf("%s", buffer-heap-malloc) richiede loop pool-read reversibile
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char src[]="copyme";int n=0;while(src[n])n++;char*dst=malloc(n+1);for(int i=0;i<=n;i++)dst[i]=src[i];printf("%s\n",dst);free(dst);return 0;}
