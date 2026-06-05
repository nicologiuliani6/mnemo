#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10];printf("%zu %zu %zu\n",sizeof(a),sizeof(a)/sizeof(a[0]),sizeof(int));return 0;}
