#!/usr/bin/env python3
"""Batch 19: globals, 2D-array fn params, chained/compound assign, enum-switch,
   unsigned wrap, pre/post inc mix, recursion accumulator, ptr to global."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# global struct array
e("pj_global_struct_arr","""
struct P{int x,y;};
struct P g[3]={{1,2},{3,4},{5,6}};
int main(void){int s=0;for(int i=0;i<3;i++)s+=g[i].x*g[i].y;g[1].x=10;s+=g[1].x;printf("%d\\n",s);return 0;}""")

# 2D array as function parameter (fixed inner dim)
e("pj_2d_param","""
int sum(int m[][3],int rows){int s=0;for(int i=0;i<rows;i++)for(int j=0;j<3;j++)s+=m[i][j];return s;}
int main(void){int a[2][3]={{1,2,3},{4,5,6}};printf("%d\\n",sum(a,2));return 0;}""")

# chained assignment a=b=c=5
e("pj_chained","""
int main(void){int a,b,c;a=b=c=5;a+=b+=c;printf("%d %d %d\\n",a,b,c);return 0;}""")

# enum in switch
e("pj_enum_switch","""
enum Color{RED,GREEN,BLUE};
int val(enum Color c){switch(c){case RED:return 100;case GREEN:return 200;case BLUE:return 300;}return 0;}
int main(void){int s=0;for(int i=0;i<3;i++)s+=val(i);printf("%d\\n",s);return 0;}""")

# unsigned overflow wrap
e("pj_uwrap","""
int main(void){unsigned a=4000000000u;unsigned b=a+a;printf("%u %u\\n",b,a*2);return 0;}""")

# pre/post inc mix
e("pj_incmix","""
int main(void){int i=5;int a=i++ + ++i;int j=10;int b=j-- - --j;printf("%d %d %d %d\\n",a,i,b,j);return 0;}""")

# recursion with accumulator
e("pj_rec_acc","""
int sumto(int n,int acc){if(n==0)return acc;return sumto(n-1,acc+n);}
int main(void){printf("%d\\n",sumto(100,0));return 0;}""")

# pointer to global, mutate
e("pj_global_ptr","""
int counter=0;
void bump(int*p,int by){*p+=by;}
int main(void){bump(&counter,5);bump(&counter,3);int*q=&counter;*q+=2;printf("%d\\n",counter);return 0;}""")

# array modification through function
e("pj_arr_modfn","""
void dbl(int*a,int n){for(int i=0;i<n;i++)a[i]*=2;}
int main(void){int x[5]={1,2,3,4,5};dbl(x,5);int s=0;for(int i=0;i<5;i++)s+=x[i];printf("%d\\n",s);return 0;}""")

# nested function calls
e("pj_nested_calls","""
int f(int x){return x+1;}int g(int x){return x*2;}int h(int x){return x-3;}
int main(void){printf("%d\\n",f(g(h(10))));return 0;}""")

print(f"generated {n} files")
