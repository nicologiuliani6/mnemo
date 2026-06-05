#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10];char c[7];struct S{int x;char y;}s;
printf("%zu %zu %zu %zu\n",sizeof(int),sizeof(a),sizeof(c),sizeof a/sizeof a[0]);return 0;}
