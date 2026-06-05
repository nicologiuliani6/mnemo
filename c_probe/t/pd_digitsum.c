#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="9876543210";int sum=0;for(int i=0;s[i];i++)sum+=s[i]-'0';printf("%d\n",sum);return 0;}
