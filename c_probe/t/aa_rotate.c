#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[6]={1,2,3,4,5,6};int k=2;int tmp[6];for(int i=0;i<6;i++)tmp[(i+k)%6]=a[i];for(int i=0;i<6;i++)printf("%d",tmp[i]);printf("\n");return 0;}
