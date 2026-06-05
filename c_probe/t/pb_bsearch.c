#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int bs(int*a,int n,int key){int lo=0,hi=n-1;while(lo<=hi){int mid=(lo+hi)/2;if(a[mid]==key)return mid;if(a[mid]<key)lo=mid+1;else hi=mid-1;}return -1;}
int main(void){int a[10]={1,3,5,7,9,11,13,15,17,19};printf("%d %d %d\n",bs(a,10,7),bs(a,10,19),bs(a,10,8));return 0;}
