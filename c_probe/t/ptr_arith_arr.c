#include <stdio.h>

int main(void){int a[5]={10,20,30,40,50};int*p=a;printf("%d %d %d\n",*p,*(p+2),*(p+4));p+=3;printf("%d\n",*p);return 0;}
