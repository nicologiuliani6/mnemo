#!/usr/bin/env python3
"""Batch 8: harder corners — fn-ptr in struct, struct-by-val w/ array field return,
   typedef ptr, enum arith, sizeof expr, manual strcmp/strcpy, qsort-like struct sort."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# function pointer stored in struct
e("p8_fnptr_in_struct","""
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
struct Op{int(*f)(int,int);int tag;};
int main(void){struct Op ops[2]={{add,1},{mul,2}};int r=0;
for(int i=0;i<2;i++)r+=ops[i].f(3,4);printf("%d\\n",r);return 0;}""")

# struct by value with array field, return
e("p8_struct_arr_return","""
struct Vec{int d[4];};
struct Vec scale(struct Vec v,int k){for(int i=0;i<4;i++)v.d[i]*=k;return v;}
int main(void){struct Vec a={{1,2,3,4}};struct Vec b=scale(a,3);
printf("%d %d %d %d | %d %d %d %d\\n",a.d[0],a.d[1],a.d[2],a.d[3],b.d[0],b.d[1],b.d[2],b.d[3]);return 0;}""")

# typedef of pointer
e("p8_typedef_ptr","""
typedef int* intptr;
int main(void){int x=42;intptr p=&x;*p=100;printf("%d\\n",x);return 0;}""")

# enum arithmetic
e("p8_enum_arith","""
enum Color{RED,GREEN=5,BLUE,YELLOW=10};
int main(void){enum Color c=GREEN;int s=RED+GREEN+BLUE+YELLOW;
printf("%d %d %d\\n",c,s,BLUE-GREEN);return 0;}""")

# sizeof in expressions
e("p8_sizeof_expr","""
int main(void){int a[10];printf("%zu %zu %zu\\n",sizeof(a),sizeof(a)/sizeof(a[0]),sizeof(int));return 0;}""")

# manual strcmp
e("p8_strcmp","""
int mycmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a-*b;}
int main(void){printf("%d %d %d\\n",mycmp("abc","abc")==0,mycmp("abc","abd")<0,mycmp("abd","abc")>0);return 0;}""")

# manual strcpy into buffer
e("p8_strcpy","""
int main(void){char dst[16];const char*src="hello";int i=0;while((dst[i]=src[i]))i++;
printf("%s %d\\n",dst,i);return 0;}""")

# bubble sort array of structs by field
e("p8_struct_sort","""
struct R{int key,val;};
int main(void){struct R a[5]={{3,30},{1,10},{4,40},{1,11},{5,50}};
for(int i=0;i<5;i++)for(int j=0;j<4-i;j++)if(a[j].key>a[j+1].key){struct R t=a[j];a[j]=a[j+1];a[j+1]=t;}
for(int i=0;i<5;i++)printf("%d:%d ",a[i].key,a[i].val);printf("\\n");return 0;}""")

# nested loops with array accumulation (matrix mult)
e("p8_matmul","""
int main(void){int A[2][2]={{1,2},{3,4}},B[2][2]={{5,6},{7,8}},C[2][2]={{0,0},{0,0}};
for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)C[i][j]+=A[i][k]*B[k][j];
printf("%d %d %d %d\\n",C[0][0],C[0][1],C[1][0],C[1][1]);return 0;}""")

# recursive gcd + iterative, compare
e("p8_gcd","""
int gcd(int a,int b){return b==0?a:gcd(b,a%b);}
int main(void){printf("%d %d %d\\n",gcd(48,36),gcd(17,5),gcd(100,80));return 0;}""")

# pointer walking a string, count + transform
e("p8_str_transform","""
int main(void){char s[]="Hello World 123";int up=0,lo=0,dg=0,sp=0;
for(char*p=s;*p;p++){if(*p>='A'&&*p<='Z')up++;else if(*p>='a'&&*p<='z')lo++;
else if(*p>='0'&&*p<='9')dg++;else sp++;}
printf("%d %d %d %d\\n",up,lo,dg,sp);return 0;}""")

# union reinterpret
e("p8_union","""
union U{int i;unsigned char b[4];};
int main(void){union U u;u.i=0x12345678;int s=0;for(int k=0;k<4;k++)s+=u.b[k];
printf("%d %02X\\n",s,u.b[0]);return 0;}""")

# 2D malloc flat indexing
e("p8_flat2d","""
int main(void){int R=4,C=5;int*g=malloc(sizeof(int)*R*C);
for(int i=0;i<R;i++)for(int j=0;j<C;j++)g[i*C+j]=i*10+j;
int s=0;for(int i=0;i<R*C;i++)s+=g[i];printf("%d\\n",s);free(g);return 0;}""")

# ternary as lvalue-ish select + chained assign
e("p8_chain_assign","""
int main(void){int a,b,c,d;a=b=c=d=7;a+=b+=c+=d+=1;printf("%d %d %d %d\\n",a,b,c,d);return 0;}""")

# const array of structs lookup
e("p8_const_lookup","""
struct KV{int k;int v;};
int lookup(int key){static const struct KV tab[4]={{1,100},{2,200},{3,300},{4,400}};
for(int i=0;i<4;i++)if(tab[i].k==key)return tab[i].v;return -1;}
int main(void){printf("%d %d %d\\n",lookup(2),lookup(4),lookup(9));return 0;}""")

print(f"generated {n} files")
