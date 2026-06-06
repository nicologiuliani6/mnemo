#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[9]={3,7,1,9,2,8,4,6,5};int mn=a[0],mx=a[0];for(int i=1;i<9;i++){if(a[i]<mn)mn=a[i];if(a[i]>mx)mx=a[i];}printf("%d %d %d\n",mn,mx,mx-mn);return 0;}
