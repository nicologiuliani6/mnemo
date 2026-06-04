#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int popcount(unsigned x){int c=0;while(x){c+=x&1;x>>=1;}return c;}
int main(void){printf("%d %d %d\n",popcount(7),popcount(255),popcount(1024));return 0;}
