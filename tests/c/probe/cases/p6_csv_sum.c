#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="10,20,30,40,50";int sum=0,cur=0;for(int i=0;;i++){if(s[i]==','||s[i]==0){sum+=cur;cur=0;if(s[i]==0)break;}else cur=cur*10+(s[i]-'0');}printf("%d\n",sum);return 0;}
