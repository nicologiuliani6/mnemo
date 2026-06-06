// SKIP overflow int 32-bit: gcc wrappa (UB) a -1651568444, mnemo (int 64-bit) tiene 11233333444 — divergenza int-width
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sign3(int x){if(x>5)return 2;if(x>0)return 1;if(x==0)return 0;return -1;}
int main(void){int s=0;for(int i=-2;i<=8;i++)s=s*10+(sign3(i)+2);printf("%d\n",s);return 0;}
