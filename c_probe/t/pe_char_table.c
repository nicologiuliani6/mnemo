// SKIP char names[3][8]={"a","b"} : 2D char array (string table) con init letterale + names[i][j] non supportato
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char names[3][8]={"alice","bob","carol"};int s=0;
for(int i=0;i<3;i++){int j=0;while(names[i][j]){s+=names[i][j];j++;}}printf("%d\n",s);return 0;}
