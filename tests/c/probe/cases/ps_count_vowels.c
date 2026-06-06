#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="the quick brown fox";int v=0;for(int i=0;s[i];i++){char c=s[i];if(c=='a'||c=='e'||c=='i'||c=='o'||c=='u')v++;}printf("%d\n",v);return 0;}
