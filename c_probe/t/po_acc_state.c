#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void acc(int*sum,int*cnt,int v){*sum+=v;*cnt+=1;}
int main(void){int sum=0,cnt=0;for(int i=1;i<=10;i++)acc(&sum,&cnt,i);printf("%d %d\n",sum,cnt);return 0;}
