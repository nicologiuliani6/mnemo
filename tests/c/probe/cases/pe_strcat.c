#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char buf[20];const char*a="foo",*b="bar";int k=0;
for(int i=0;a[i];i++)buf[k++]=a[i];for(int i=0;b[i];i++)buf[k++]=b[i];buf[k]=0;
printf("%s %d\n",buf,k);return 0;}
