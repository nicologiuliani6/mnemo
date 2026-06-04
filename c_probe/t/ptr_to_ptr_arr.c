#include <stdio.h>

int main(void){int x=1,y=2,z=3;int*a[3]={&x,&y,&z};int s=0;for(int i=0;i<3;i++)s+=*a[i];printf("%d\n",s);return 0;}
