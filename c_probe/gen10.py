#!/usr/bin/env python3
"""Batch 10: typedef struct, nested member chains, ptr-to-ptr, 3D array,
   enum switch, const lookup, string builtins, complex init, qsort-like."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# typedef struct
e("pa_typedef_struct","""
typedef struct{int x,y;}Point;
int main(void){Point p={3,4};Point q=p;q.x=10;printf("%d %d %d %d\\n",p.x,p.y,q.x,q.y);return 0;}""")

# nested struct member chain
e("pa_nested_chain","""
struct A{int v;};struct B{struct A a;int w;};struct C{struct B b;int z;};
int main(void){struct C c={{{5},6},7};c.b.a.v=50;printf("%d %d %d\\n",c.b.a.v,c.b.w,c.z);return 0;}""")

# pointer to pointer modification
e("pa_ptr_ptr","""
void set(int**pp,int*target){*pp=target;}
int main(void){int a=1,b=2;int*p=&a;set(&p,&b);*p=99;printf("%d %d\\n",a,b);return 0;}""")

# 3D array
e("pa_3d_array","""
int main(void){int t[2][2][2];int c=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)t[i][j][k]=c++;
int s=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)s+=t[i][j][k]*(i+j+k+1);printf("%d\\n",s);return 0;}""")

# enum in switch
e("pa_enum_switch","""
enum Op{ADD,SUB,MUL,DIV};
int calc(enum Op o,int a,int b){switch(o){case ADD:return a+b;case SUB:return a-b;case MUL:return a*b;case DIV:return a/b;}return 0;}
int main(void){printf("%d %d %d %d\\n",calc(ADD,6,3),calc(SUB,6,3),calc(MUL,6,3),calc(DIV,6,3));return 0;}""")

# strlen/strcmp builtins
e("pa_str_builtin","""
int main(void){const char*a="hello";printf("%zu %d %d\\n",strlen(a),strcmp("abc","abc"),strcmp("abc","abd"));return 0;}""")

# const lookup table
e("pa_const_table","""
int main(void){const int sq[8]={0,1,4,9,16,25,36,49};int s=0;for(int i=0;i<8;i++)s+=sq[i];printf("%d\\n",s);return 0;}""")

# bubble sort ints
e("pa_bubble","""
int main(void){int a[8]={5,2,8,1,9,3,7,4};
for(int i=0;i<8;i++)for(int j=0;j<7-i;j++)if(a[j]>a[j+1]){int t=a[j];a[j]=a[j+1];a[j+1]=t;}
for(int i=0;i<8;i++)printf("%d",a[i]);printf("\\n");return 0;}""")

# fibonacci iterative + matrix-style
e("pa_fib_iter","""
int main(void){int a=0,b=1;for(int i=0;i<15;i++){int t=a+b;a=b;b=t;}printf("%d %d\\n",a,b);return 0;}""")

# nested ternary with function calls
e("pa_ternary_call","""
int f(int x){return x*x;}int g(int x){return x+1;}
int main(void){int s=0;for(int i=-2;i<=2;i++)s+=(i<0?f(i):i==0?100:g(i));printf("%d\\n",s);return 0;}""")

# multi-dim struct array
e("pa_struct_2d","""
struct Cell{int v,m;};
int main(void){struct Cell grid[3][3];for(int i=0;i<3;i++)for(int j=0;j<3;j++){grid[i][j].v=i*3+j;grid[i][j].m=(i==j);}
int s=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++)if(grid[i][j].m)s+=grid[i][j].v;printf("%d\\n",s);return 0;}""")

# while with complex condition
e("pa_while_cond","""
int main(void){int x=1000,steps=0;while(x>1&&steps<100){if(x%2==0)x/=2;else x=3*x+1;steps++;}printf("%d %d\\n",x,steps);return 0;}""")

# array slice sum via pointers
e("pa_slice","""
static int sum(const int*p,int n){int s=0;while(n--)s+=*p++;return s;}
int main(void){int a[10]={1,2,3,4,5,6,7,8,9,10};printf("%d %d %d\\n",sum(a,10),sum(a+3,4),sum(a,0));return 0;}""")

# char frequency count
e("pa_char_freq","""
int main(void){const char*s="mississippi";int f[26]={0};for(int i=0;s[i];i++)f[s[i]-'a']++;
printf("%d %d %d %d\\n",f['m'-'a'],f['i'-'a'],f['s'-'a'],f['p'-'a']);return 0;}""")

# unsigned right shift vs signed
e("pa_shift_sign","""
int main(void){int a=-16;unsigned b=0xFFFFFFF0u;printf("%d %u %d\\n",a>>2,b>>2,(-100)>>3);return 0;}""")

# static local persistence
e("pa_static_persist","""
int next(void){static int s=1;s=s*2+1;return s;}
int main(void){for(int i=0;i<6;i++)printf("%d ",next());printf("\\n");return 0;}""")

print(f"generated {n} files")
