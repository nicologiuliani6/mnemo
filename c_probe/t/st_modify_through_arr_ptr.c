#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int v;};
void incall(struct P*a,int n){for(int i=0;i<n;i++)a[i].v++;}
int main(void){struct P a[3]={{10},{20},{30}};incall(a,3);printf("%d %d %d\n",a[0].v,a[1].v,a[2].v);return 0;}
