#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Stack{int data[10];int top;};
int main(void){struct Stack s;s.top=0;for(int i=0;i<5;i++){s.data[s.top]=i*i;s.top++;}int sum=0;while(s.top>0){s.top--;sum+=s.data[s.top];}printf("%d\n",sum);return 0;}
