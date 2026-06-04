#include <stdio.h>

int main(void){int a[4]={1,2,3,4};int*p=a;int s=0;for(int i=0;i<4;i++){s+=*p;p++;}printf("%d\n",s);return 0;}
