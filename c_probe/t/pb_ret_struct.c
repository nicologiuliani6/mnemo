#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Pair{int sum,prod;};
struct Pair compute(int a,int b){struct Pair p;p.sum=a+b;p.prod=a*b;return p;}
int main(void){struct Pair r=compute(7,6);printf("%d %d\n",r.sum,r.prod);return 0;}
