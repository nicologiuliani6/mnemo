#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*words[3]={"cat","dog","bird"};int total=0;
for(int i=0;i<3;i++)for(int j=0;words[i][j];j++)total++;printf("%d\n",total);return 0;}
