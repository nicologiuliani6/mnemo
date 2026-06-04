#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){const char*s="3+4*2-1";int vals[8],vn=0,ops[8],on=0,i=0;
while(s[i]){int num=0;while(s[i]>='0'&&s[i]<='9'){num=num*10+(s[i]-'0');i++;}vals[vn++]=num;if(s[i])ops[on++]=s[i++];}
int res=vals[0];for(int k=0;k<on;k++){if(ops[k]=='+')res+=vals[k+1];else if(ops[k]=='-')res-=vals[k+1];else if(ops[k]=='*')res*=vals[k+1];}printf("%d\n",res);return 0;}
