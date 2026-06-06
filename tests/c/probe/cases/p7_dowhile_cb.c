#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int i=0,s=0;do{i++;if(i%2==0)continue;if(i>9)break;s+=i;}while(i<20);printf("%d\n",s);return 0;}
