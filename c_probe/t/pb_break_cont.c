#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int found=0,fi=0,fj=0;for(int i=0;i<10;i++){for(int j=0;j<10;j++){if(i*j==12){found=1;fi=i;fj=j;break;}}if(found)break;}
printf("%d %d %d\n",found,fi,fj);return 0;}
