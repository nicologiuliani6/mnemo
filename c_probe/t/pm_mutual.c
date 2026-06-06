#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int is_even(int n);int is_odd(int n){return n==0?0:is_even(n-1);}
int is_even(int n){return n==0?1:is_odd(n-1);}
int main(void){printf("%d %d %d\n",is_even(10),is_odd(7),is_even(0));return 0;}
