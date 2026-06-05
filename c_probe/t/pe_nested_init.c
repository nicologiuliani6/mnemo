#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Inner{int a,b;};struct Outer{struct Inner i;int arr[3];int z;};
int main(void){struct Outer o={{1,2},{3,4,5},6};printf("%d %d %d %d %d %d\n",o.i.a,o.i.b,o.arr[0],o.arr[1],o.arr[2],o.z);return 0;}
