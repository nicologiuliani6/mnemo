#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int data[10];
void fill(int start){for(int i=0;i<10;i++)data[i]=start+i;}
int sum(void){int s=0;for(int i=0;i<10;i++)s+=data[i];return s;}
int main(void){fill(100);printf("%d ",sum());fill(0);printf("%d\n",sum());return 0;}
