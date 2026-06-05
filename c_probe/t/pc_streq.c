#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int streq(const char*a,const char*b){int i=0;while(a[i]&&a[i]==b[i])i++;return a[i]==b[i];}
int main(void){printf("%d %d %d\n",streq("hello","hello"),streq("hello","world"),streq("ab","abc"));return 0;}
