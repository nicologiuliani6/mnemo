#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int st=0,steps=0,x=0;while(st!=3&&steps<100){steps++;switch(st){
case 0:x+=1;st=1;break;case 1:x*=2;st=2;break;case 2:x-=1;if(x>20)st=3;else st=0;break;}}
printf("%d %d\n",x,steps);return 0;}
