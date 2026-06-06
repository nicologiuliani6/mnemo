#include <stdio.h>

int main(void){int i=0,s=0;while(i<5){s+=i;i++;}int j=0;do{s+=j;j++;}while(j<3);printf("%d\n",s);return 0;}
