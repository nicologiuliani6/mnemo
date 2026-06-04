#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(unsigned x=0;x<256;x++){unsigned t=x,c=0;while(t){c+=t&1;t>>=1;}s+=c;}printf("%d\n",s);return 0;}
