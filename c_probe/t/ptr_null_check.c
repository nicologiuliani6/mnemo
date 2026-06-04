#include <stdio.h>

int main(void){int*p=0;if(p==0)printf("null\n");int x=1;p=&x;if(p)printf("set %d\n",*p);return 0;}
