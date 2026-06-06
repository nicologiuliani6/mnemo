#!/usr/bin/env python3
"""Batch 17: non-malloc corners — struct return byval, ptr-to-array, 2D index
   expr, char/string edges, nested ternary lvalue, comma op, compound conditions."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# struct returned by value from function
e("ph_struct_ret","""
struct P{int x,y;};
struct P mk(int a,int b){struct P p;p.x=a;p.y=b;return p;}
int main(void){struct P q=mk(3,7);printf("%d %d %d\\n",q.x,q.y,q.x+q.y);return 0;}""")

# pointer to fixed array, row pointer
e("ph_row_ptr","""
int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;
int(*r)[4]=m;int s=0;for(int i=0;i<3;i++)for(int j=0;j<4;j++)s+=r[i][j];printf("%d\\n",s);return 0;}""")

# 2D index with arithmetic expression
e("ph_2d_idxexpr","""
int main(void){int a[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)a[i][j]=i*4+j;
int s=0;for(int k=0;k<4;k++)s+=a[k][3-k];printf("%d\\n",s);return 0;}""")

# comma operator in for
e("ph_comma","""
int main(void){int s=0;for(int i=0,j=10;i<j;i++,j--)s+=i*j;printf("%d\\n",s);return 0;}""")

# nested ternary as array index
e("ph_ternary_idx","""
int main(void){int a[5]={10,20,30,40,50};int s=0;for(int i=0;i<5;i++)s+=a[i<2?0:i<4?2:4];printf("%d\\n",s);return 0;}""")

# char array fill and modify in place
e("ph_char_mod","""
int main(void){char s[10];for(int i=0;i<9;i++)s[i]='a'+i;s[9]=0;
for(int i=0;i<9;i++)if(s[i]%2==0)s[i]-=32;printf("%s\\n",s);return 0;}""")

# compound bool conditions short-circuit side-effect
e("ph_shortcircuit","""
int cnt=0;int f(int x){cnt++;return x;}
int main(void){int a=f(0)&&f(1);int b=f(1)||f(0);printf("%d %d %d\\n",a,b,cnt);return 0;}""")

# multi-return struct with array field
e("ph_struct_arr_ret","""
struct V{int d[3];};
struct V add(struct V a,struct V b){struct V r;for(int i=0;i<3;i++)r.d[i]=a.d[i]+b.d[i];return r;}
int main(void){struct V x={{1,2,3}},y={{10,20,30}};struct V z=add(x,y);printf("%d %d %d\\n",z.d[0],z.d[1],z.d[2]);return 0;}""")

# pointer comparison and difference
e("ph_ptr_diff","""
int main(void){int a[8]={0,1,2,3,4,5,6,7};int*p=&a[2];int*q=&a[6];
printf("%d %d %d\\n",(int)(q-p),*p,*q);return 0;}""")

# switch fallthrough accumulate
e("ph_switch_fall","""
int main(void){int s=0;for(int i=0;i<5;i++){switch(i){case 0:s+=1;case 1:s+=2;break;case 2:s+=4;default:s+=8;}}printf("%d\\n",s);return 0;}""")

# bit manipulation: set/clear/toggle
e("ph_bitops","""
int main(void){unsigned x=0;x|=(1<<3);x|=(1<<5);x&=~(1<<3);x^=(1<<7);
printf("%u %d\\n",x,__builtin_popcount(x));return 0;}""")

# nested struct pointer chain
e("ph_struct_chain","""
struct B{int v;};struct A{struct B*b;};
int main(void){struct B b={42};struct A a;a.b=&b;a.b->v+=8;printf("%d\\n",a.b->v);return 0;}""")

print(f"generated {n} files")
