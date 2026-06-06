#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sq(int x){return x*x;}int cube(int x){return x*x*x;}
int apply_n(int(*f)(int),int x,int n){for(int i=0;i<n;i++)x=f(x);return x;}
int main(void){printf("%d %d\n",apply_n(sq,2,3),apply_n(cube,2,2));return 0;}
