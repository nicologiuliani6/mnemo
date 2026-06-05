#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="mississippi";int f[26]={0};for(int i=0;s[i];i++)f[s[i]-'a']++;
printf("%d %d %d %d\n",f['m'-'a'],f['i'-'a'],f['s'-'a'],f['p'-'a']);return 0;}
