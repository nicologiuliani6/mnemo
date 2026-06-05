#!/usr/bin/env python3
"""Batch 12: fn-ptr typedef/return, mem* manuali, malloc patterns, bitfield,
   compound literal, designated, mutual rec, multi-deref, char buffer."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# typedef function pointer
e("pc_fnptr_typedef","""
typedef int(*BinOp)(int,int);
int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int apply(BinOp f,int a,int b){return f(a,b);}
int main(void){printf("%d %d\\n",apply(add,7,3),apply(sub,7,3));return 0;}""")

# manual memcpy
e("pc_memcpy","""
int main(void){int src[5]={10,20,30,40,50},dst[5];
for(int i=0;i<5;i++)dst[i]=src[i];int s=0;for(int i=0;i<5;i++)s+=dst[i];printf("%d\\n",s);return 0;}""")

# manual memset
e("pc_memset","""
int main(void){int a[8];for(int i=0;i<8;i++)a[i]=7;a[3]=99;int s=0;for(int i=0;i<8;i++)s+=a[i];printf("%d\\n",s);return 0;}""")

# malloc array of structs
e("pc_malloc_structs","""
struct Item{int id,qty;};
int main(void){int n=5;struct Item*items=malloc(sizeof(struct Item)*n);
for(int i=0;i<n;i++){items[i].id=i;items[i].qty=(i+1)*10;}
int s=0;for(int i=0;i<n;i++)s+=items[i].id*items[i].qty;printf("%d\\n",s);free(items);return 0;}""")

# bitfield (real)
e("pc_bitfield","""
struct Flags{unsigned a:3;unsigned b:5;unsigned c:8;};
int main(void){struct Flags f;f.a=5;f.b=20;f.c=200;printf("%u %u %u\\n",f.a,f.b,f.c);return 0;}""")

# designated array init
e("pc_desig_arr","""
int main(void){int a[10]={[0]=1,[9]=10,[5]=5,[3]=3};int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d\\n",s);return 0;}""")

# mutual recursion
e("pc_mutual","""
int is_even(int n);int is_odd(int n);
int is_even(int n){return n==0?1:is_odd(n-1);}
int is_odd(int n){return n==0?0:is_even(n-1);}
int main(void){printf("%d %d %d %d\\n",is_even(10),is_odd(10),is_even(7),is_odd(7));return 0;}""")

# multi-level pointer deref
e("pc_multideref","""
int main(void){int x=42;int*p=&x;int**pp=&p;int***ppp=&pp;***ppp=100;printf("%d %d %d\\n",x,*p,**pp);return 0;}""")

# char buffer manipulation
e("pc_char_buf","""
int main(void){char buf[20];int i=0;for(int v=12345;v>0;v/=10)buf[i++]=v%10+'0';buf[i]=0;
for(int a=0,b=i-1;a<b;a++,b--){char t=buf[a];buf[a]=buf[b];buf[b]=t;}printf("%s\\n",buf);return 0;}""")

# accumulator recursion
e("pc_acc_rec","""
int fact_acc(int n,int acc){return n<=1?acc:fact_acc(n-1,acc*n);}
int main(void){printf("%d %d\\n",fact_acc(5,1),fact_acc(7,1));return 0;}""")

# pointer comparison sort (selection)
e("pc_selection","""
int main(void){int a[7]={64,25,12,22,11,90,1};
for(int i=0;i<6;i++){int mi=i;for(int j=i+1;j<7;j++)if(a[j]<a[mi])mi=j;int t=a[i];a[i]=a[mi];a[mi]=t;}
for(int i=0;i<7;i++)printf("%d ",a[i]);printf("\\n");return 0;}""")

# nested struct array in struct
e("pc_struct_nest_arr","""
struct Row{int cells[4];};struct Grid{struct Row rows[3];};
int main(void){struct Grid g;for(int i=0;i<3;i++)for(int j=0;j<4;j++)g.rows[i].cells[j]=i*4+j;
int s=0;for(int i=0;i<3;i++)for(int j=0;j<4;j++)s+=g.rows[i].cells[j];printf("%d\\n",s);return 0;}""")

# compound conditions short circuit
e("pc_short_circuit","""
int calls=0;int chk(int x){calls++;return x>0;}
int main(void){int a=chk(1)&&chk(2)&&chk(-1)&&chk(3);int b=chk(-1)||chk(0)||chk(5);
printf("%d %d %d\\n",a,b,calls);return 0;}""")

# uint8/uint16 wrap
e("pc_uint_wrap","""
int main(void){uint8_t a=250;a+=10;uint16_t b=65530;b+=10;printf("%u %u\\n",a,b);return 0;}""")

# function returning function pointer (via param-resolved)
e("pc_dispatch_arr","""
int sq(int x){return x*x;}int cube(int x){return x*x*x;}int neg(int x){return -x;}
int main(void){int(*ops[3])(int)={sq,cube,neg};int s=0;for(int i=0;i<3;i++)s+=ops[i](3);printf("%d\\n",s);return 0;}""")

# string compare loop
e("pc_streq","""
int streq(const char*a,const char*b){int i=0;while(a[i]&&a[i]==b[i])i++;return a[i]==b[i];}
int main(void){printf("%d %d %d\\n",streq("hello","hello"),streq("hello","world"),streq("ab","abc"));return 0;}""")

print(f"generated {n} files")
