#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int q[8],head=0,tail=0,cnt=0;for(int i=0;i<5;i++){q[tail]=i*10;tail=(tail+1)%8;cnt++;}int s=0;while(cnt){s+=q[head];head=(head+1)%8;cnt--;}printf("%d\n",s);return 0;}
