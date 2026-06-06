#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a[5]={[0]=1,[4]=5,[2]=3};for(int i=0;i<5;i++)printf("%d",a[i]);printf("\n");return 0;}
