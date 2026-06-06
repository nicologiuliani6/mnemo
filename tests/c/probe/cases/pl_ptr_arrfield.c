#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct B{int data[5];};
int main(void){struct B b;struct B*p=&b;for(int i=0;i<5;i++)p->data[i]=i*i;
int s=0;for(int i=0;i<5;i++)s+=p->data[i];printf("%d\n",s);return 0;}
