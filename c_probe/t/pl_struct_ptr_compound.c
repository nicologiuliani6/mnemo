#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct C{int cnt;};
void inc(struct C*c,int by){c->cnt+=by;}
int main(void){struct C c={0};for(int i=1;i<=5;i++)inc(&c,i);printf("%d\n",c.cnt);return 0;}
