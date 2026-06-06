#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int data[10]={3,1,4,1,5,9,2,6,5,3};int h[10]={0};for(int i=0;i<10;i++)h[data[i]]++;int mx=0,mxv=0;for(int i=0;i<10;i++)if(h[i]>mx){mx=h[i];mxv=i;}printf("%d %d\n",mxv,mx);return 0;}
