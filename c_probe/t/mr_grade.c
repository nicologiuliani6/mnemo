#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

char grade(int s){if(s>=90)return 'A';if(s>=80)return 'B';if(s>=70)return 'C';if(s>=60)return 'D';return 'F';}
int main(void){int sc[5]={95,82,71,55,68};for(int i=0;i<5;i++)printf("%c",grade(sc[i]));printf("\n");return 0;}
