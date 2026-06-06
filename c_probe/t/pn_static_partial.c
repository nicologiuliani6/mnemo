#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){static int a[10]={1,2,3};int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d\n",s);return 0;}
