#include <stdio.h>

#define tn(x) _Generic((x),int:"int",char:"char",unsigned:"uint",default:"?")
int main(void){int a=1;char c='x';unsigned u=2;printf("%s %s %s\n",tn(a),tn(c),tn(u));return 0;}
