#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int a[15]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15};
int ts(int i){if(i>=15)return 0;return a[i]+ts(2*i+1)+ts(2*i+2);}
int main(void){printf("%d\n",ts(0));return 0;}
