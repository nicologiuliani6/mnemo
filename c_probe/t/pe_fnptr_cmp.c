#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int main(void){int(*f)(int,int)=add;int eq=(f==add);int ne=(f!=sub);printf("%d %d %d\n",eq,ne,f(3,2));return 0;}
