#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int st[100],top=0;for(int i=1;i<=10;i++)st[top++]=i*i;int s=0;while(top)s+=st[--top];printf("%d\n",s);return 0;}
