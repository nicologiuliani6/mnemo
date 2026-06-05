#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int i=0,s=0;do{i++;if(i==7)break;if(i%2==0)continue;s+=i;}while(i<100);printf("%d %d\n",s,i);return 0;}
