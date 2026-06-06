#!/usr/bin/env python3
"""Batch 21: fn-ptr in struct, returned-struct field, multi-deref, printf %c/%x,
   p->arr[i], char switch, bitwise signed, compound on struct ptr field."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# function pointer stored in struct field
e("pl_fnptr_struct","""
struct Op{int(*f)(int,int);};
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int main(void){struct Op o;o.f=add;int x=o.f(3,4);o.f=mul;int y=o.f(3,4);printf("%d %d\\n",x,y);return 0;}""")

# use returned struct field directly mk().x
e("pl_ret_field","""
struct P{int x,y;};
struct P mk(int a){struct P p;p.x=a;p.y=a*a;return p;}
int main(void){struct P q=mk(5);printf("%d %d\\n",q.x,q.y);return 0;}""")

# multi-level dereference int**
e("pl_multideref","""
int main(void){int x=42;int*p=&x;int**pp=&p;**pp=100;(**pp)+=5;printf("%d\\n",x);return 0;}""")

# printf %c and %x
e("pl_printf_fmt","""
int main(void){char c='A';int x=255;printf("%c %x %X\\n",c,x,x);return 0;}""")

# p->arr[i] pointer to struct with array field
e("pl_ptr_arrfield","""
struct B{int data[5];};
int main(void){struct B b;struct B*p=&b;for(int i=0;i<5;i++)p->data[i]=i*i;
int s=0;for(int i=0;i<5;i++)s+=p->data[i];printf("%d\\n",s);return 0;}""")

# switch on char
e("pl_char_switch","""
int main(void){const char*s="abcabc";int s1=0;for(int i=0;s[i];i++){switch(s[i]){case 'a':s1+=1;break;case 'b':s1+=10;break;case 'c':s1+=100;break;}}printf("%d\\n",s1);return 0;}""")

# bitwise on signed negative
e("pl_bitsigned","""
int main(void){int a=-1;int b=a&0xFF;int c=(-8)>>1;int d=~0;printf("%d %d %d\\n",b,c,d);return 0;}""")

# compound assign on struct pointer field
e("pl_struct_ptr_compound","""
struct C{int cnt;};
void inc(struct C*c,int by){c->cnt+=by;}
int main(void){struct C c={0};for(int i=1;i<=5;i++)inc(&c,i);printf("%d\\n",c.cnt);return 0;}""")

# array of function pointers in struct
e("pl_fnptr_arr_struct","""
int f0(int x){return x;}int f1(int x){return x*2;}int f2(int x){return x+10;}
struct T{int(*ops[3])(int);};
int main(void){struct T t;t.ops[0]=f0;t.ops[1]=f1;t.ops[2]=f2;int v=5;
for(int i=0;i<3;i++)v=t.ops[i](v);printf("%d\\n",v);return 0;}""")

# ternary with function calls
e("pl_ternary_call","""
int sq(int x){return x*x;}int cube(int x){return x*x*x;}
int main(void){int s=0;for(int i=1;i<=4;i++)s+=(i%2)?sq(i):cube(i);printf("%d\\n",s);return 0;}""")

print(f"generated {n} files")
