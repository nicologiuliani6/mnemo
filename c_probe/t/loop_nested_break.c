#include <stdio.h>

int main(void){int c=0;for(int i=0;i<5;i++){for(int j=0;j<5;j++){if(j==3)break;c++;}}printf("%d\n",c);return 0;}
