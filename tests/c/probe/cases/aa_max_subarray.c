#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[8]={-2,1,-3,4,-1,2,1,-5};int best=a[0],cur=a[0];for(int i=1;i<8;i++){cur=a[i]>cur+a[i]?a[i]:cur+a[i];if(cur>best)best=cur;}printf("%d\n",best);return 0;}
