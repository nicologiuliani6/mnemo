#!/usr/bin/env python3
"""Batch 20: typedef struct, nested array-in-struct via ptr, var shift, sizeof
   in expr, ptr aliasing, ternary ptr, const arrays, struct ptr increment."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# typedef struct + pointer
e("pk_typedef_struct","""
typedef struct{int a,b;}Pair;
int main(void){Pair p={3,4};Pair*q=&p;q->a+=10;printf("%d %d\\n",p.a,q->b);return 0;}""")

# array field in struct, access via pointer
e("pk_struct_arrfield_ptr","""
struct V{int d[4];};
int main(void){struct V v={{1,2,3,4}};struct V*p=&v;int s=0;for(int i=0;i<4;i++)s+=p->d[i];p->d[0]=100;s+=p->d[0];printf("%d\\n",s);return 0;}""")

# variable shift amount
e("pk_varshift","""
int main(void){int s=0;for(int i=0;i<8;i++)s+=(1<<i);unsigned x=0xFF00;for(int i=0;i<4;i++)s+=(x>>(i*4))&0xF;printf("%d\\n",s);return 0;}""")

# sizeof in expressions
e("pk_sizeof_expr","""
int main(void){int a[10];int n=sizeof(a)/sizeof(a[0]);int b=sizeof(int)*2;printf("%d %d\\n",n,b);return 0;}""")

# pointer aliasing same memory
e("pk_alias","""
int main(void){int x=5;int*p=&x;int*q=p;*p=10;*q+=5;printf("%d\\n",x);return 0;}""")

# ternary returning pointer
e("pk_ternary_ptr","""
int main(void){int a=1,b=2;int*p=(a<b)?&a:&b;*p=99;printf("%d %d\\n",a,b);return 0;}""")

# const array readonly
e("pk_const_arr","""
int main(void){const int lut[5]={2,3,5,7,11};int s=0;for(int i=0;i<5;i++)s+=lut[i]*i;printf("%d\\n",s);return 0;}""")

# struct pointer increment over array
e("pk_structptr_inc","""
struct P{int x,y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a;int s=0;
for(int i=0;i<3;i++){s+=p->x+p->y;p++;}printf("%d\\n",s);return 0;}""")

# typedef pointer
e("pk_typedef_ptr","""
typedef int* intptr;
int main(void){int x=42;intptr p=&x;*p+=8;printf("%d\\n",x);return 0;}""")

# nested struct in array of struct, deep field
e("pk_deep_field","""
struct Inner{int v;};struct Outer{struct Inner in;int tag;};
int main(void){struct Outer arr[3];for(int i=0;i<3;i++){arr[i].in.v=i*10;arr[i].tag=i;}
int s=0;for(int i=0;i<3;i++)s+=arr[i].in.v+arr[i].tag;printf("%d\\n",s);return 0;}""")

print(f"generated {n} files")
