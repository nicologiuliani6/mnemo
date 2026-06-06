#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char buf[]="SECRET";unsigned char k=0x5A;for(int i=0;buf[i];i++)buf[i]^=k;for(int i=0;buf[i];i++)buf[i]^=k;printf("%s\n",buf);return 0;}
