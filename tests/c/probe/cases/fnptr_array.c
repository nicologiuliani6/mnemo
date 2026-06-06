#include <stdio.h>

int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int main(void){int(*ops[2])(int,int)={add,sub};for(int i=0;i<2;i++)printf("%d ",ops[i](10,3));printf("\n");return 0;}
