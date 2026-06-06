#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char*pick(int k){return k?"on":"off";}
int main(void){printf("%s %s\n",pick(1),pick(0));return 0;}
