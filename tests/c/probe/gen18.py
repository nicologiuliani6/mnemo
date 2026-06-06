#!/usr/bin/env python3
"""Batch 18: strings manual, static locals, negatives/mod, nested struct-ptr,
   fn-ptr return, ptr-to-ptr param, array-of-struct-ptr, const folding."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# static local counter
e("pi_static","""
int next(void){static int c=0;c++;return c;}
int main(void){int s=0;for(int i=0;i<5;i++)s+=next();printf("%d\\n",s);return 0;}""")

# manual strlen + strcmp
e("pi_strfns","""
int slen(const char*s){int n=0;while(s[n])n++;return n;}
int scmp(const char*a,const char*b){int i=0;while(a[i]&&a[i]==b[i])i++;return a[i]-b[i];}
int main(void){printf("%d %d %d\\n",slen("hello"),scmp("abc","abc"),scmp("abd","abc"));return 0;}""")

# negative modulo and division
e("pi_negmod","""
int main(void){int a=-17,b=5;printf("%d %d %d %d\\n",a/b,a%b,-a/b,-a%b);return 0;}""")

# function returning function pointer
e("pi_fnptr_ret","""
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int(*pick(int op))(int,int){return op?mul:add;}
int main(void){int(*f)(int,int)=pick(1);int(*g)(int,int)=pick(0);printf("%d %d\\n",f(3,4),g(3,4));return 0;}""")

# pointer-to-pointer parameter modification
e("pi_pp_param","""
void inc(int**p){(**p)++;}
int main(void){int x=10;int*q=&x;inc(&q);printf("%d\\n",x);return 0;}""")

# array of struct pointers
e("pi_arr_structptr","""
struct N{int v;};
int main(void){struct N a={1},b={2},c={3};struct N*arr[3]={&a,&b,&c};
int s=0;for(int i=0;i<3;i++)s+=arr[i]->v;arr[1]->v=20;s+=arr[1]->v;printf("%d\\n",s);return 0;}""")

# nested struct ptr two levels
e("pi_nested2","""
struct C{int v;};struct B{struct C*c;};struct A{struct B*b;};
int main(void){struct C c={7};struct B b;b.c=&c;struct A a;a.b=&b;
a.b->c->v*=6;printf("%d\\n",a.b->c->v);return 0;}""")

# const folding and large constants
e("pi_constfold","""
int main(void){int a=(2+3)*4-1;int b=100/7;int c=1<<10;printf("%d %d %d\\n",a,b,c);return 0;}""")

# string reverse in place
e("pi_strrev","""
int main(void){char s[]="abcdef";int n=0;while(s[n])n++;
for(int i=0,j=n-1;i<j;i++,j--){char t=s[i];s[i]=s[j];s[j]=t;}printf("%s\\n",s);return 0;}""")

# multidim array passed to function as flat
e("pi_md_func","""
int sum2d(int*p,int n){int s=0;for(int i=0;i<n;i++)s+=p[i];return s;}
int main(void){int m[2][3]={{1,2,3},{4,5,6}};printf("%d\\n",sum2d(&m[0][0],6));return 0;}""")

print(f"generated {n} files")
