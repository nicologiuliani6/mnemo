#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char src[]="hello world";char dst[6];int i;for(i=0;i<5&&src[i];i++)dst[i]=src[i];dst[i]=0;printf("%s %d\n",dst,i);return 0;}
