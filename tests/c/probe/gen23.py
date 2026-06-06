#!/usr/bin/env python3
"""Batch 23: linked-list-via-array, void* cast, ptr diff structs, 3D malloc,
   strchr manual, integer promo, static array init, nested malloc free order."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# linked list via index-based nodes
e("pn_linklist","""
struct Node{int val,next;};
int main(void){struct Node pool[5]={{10,1},{20,2},{30,3},{40,4},{50,-1}};
int cur=0,s=0;while(cur!=-1){s+=pool[cur].val;cur=pool[cur].next;}printf("%d\\n",s);return 0;}""")

# void* cast roundtrip
e("pn_voidcast","""
int main(void){int x=42;void*v=&x;int*p=(int*)v;*p+=8;printf("%d\\n",x);return 0;}""")

# pointer difference between struct elements
e("pn_structdiff","""
struct P{int x,y;};
int main(void){struct P a[10];struct P*p=&a[2];struct P*q=&a[7];printf("%d\\n",(int)(q-p));return 0;}""")

# 3D malloc
e("pn_3d_malloc","""
int main(void){int A=2,B=2,C=2;int***g=malloc(sizeof(int**)*A);
for(int i=0;i<A;i++){g[i]=malloc(sizeof(int*)*B);for(int j=0;j<B;j++){g[i][j]=malloc(sizeof(int)*C);
for(int k=0;k<C;k++)g[i][j][k]=i*4+j*2+k;}}
int s=0;for(int i=0;i<A;i++)for(int j=0;j<B;j++)for(int k=0;k<C;k++)s+=g[i][j][k];
printf("%d\\n",s);return 0;}""")

# strchr manual
e("pn_strchr","""
int find(const char*s,char c){for(int i=0;s[i];i++)if(s[i]==c)return i;return -1;}
int main(void){printf("%d %d %d\\n",find("hello",'l'),find("world",'z'),find("abc",'a'));return 0;}""")

# integer promotion char arithmetic
e("pn_promo","""
int main(void){char a=100,b=100;int c=a+b;char d=a+b;printf("%d %d\\n",c,d);return 0;}""")

# static array with partial init
e("pn_static_partial","""
int main(void){static int a[10]={1,2,3};int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d\\n",s);return 0;}""")

# malloc free reuse
e("pn_malloc_reuse","""
int main(void){int s=0;for(int k=0;k<3;k++){int*a=malloc(sizeof(int)*4);
for(int i=0;i<4;i++)a[i]=k*4+i;for(int i=0;i<4;i++)s+=a[i];free(a);}printf("%d\\n",s);return 0;}""")

# nested array index with function
e("pn_idx_func","""
int idx(int i){return (i*7)%10;}
int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i*i;int s=0;for(int i=0;i<10;i++)s+=a[idx(i)];printf("%d\\n",s);return 0;}""")

# unsigned/signed mix comparison
e("pn_signmix","""
int main(void){int a=-1;unsigned b=1;int r1=(a<(int)b);unsigned c=10,d=20;int r2=(c-d>5);
printf("%d %d %u\\n",r1,r2,c-d);return 0;}""")

print(f"generated {n} files")
