#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[7]={4,8,15,16,23,42,8};int sum=0,mn=a[0],mx=a[0];for(int i=0;i<7;i++){sum+=a[i];if(a[i]<mn)mn=a[i];if(a[i]>mx)mx=a[i];}printf("%d %d %d %d\n",sum,sum/7,mn,mx);return 0;}
