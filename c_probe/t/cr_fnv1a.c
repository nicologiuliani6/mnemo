// SKIP-NONATIVE: fnv mult per costante grande = O(const) senza --native-arith (corretto con native)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

unsigned fnv(const char*s){unsigned h=2166136261u;while(*s){h^=(unsigned char)*s++;h*=16777619u;}return h;}
int main(void){printf("%u\n",fnv("hello"));return 0;}
