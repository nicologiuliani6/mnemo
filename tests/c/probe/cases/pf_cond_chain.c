#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int grade(int s){return s>=90?4:s>=80?3:s>=70?2:s>=60?1:0;}
int main(void){int t=0;int scores[5]={95,82,71,55,88};for(int i=0;i<5;i++)t=t*10+grade(scores[i]);printf("%d\n",t);return 0;}
