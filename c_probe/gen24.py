#!/usr/bin/env python3
"""Batch 24: nested call in condition, struct array param, ptr-to-ptr return,
   bit fields via masks, 2D malloc partial, char* array iterate, accumulator fns."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# nested function call in loop condition
e("po_call_cond","""
int more(int i){return i<10;}
int main(void){int s=0;for(int i=0;more(i);i++)s+=i;printf("%d\\n",s);return 0;}""")

# struct array as function parameter
e("po_struct_arr_param","""
struct P{int x,y;};
int total(struct P*a,int n){int s=0;for(int i=0;i<n;i++)s+=a[i].x+a[i].y;return s;}
int main(void){struct P arr[3]={{1,2},{3,4},{5,6}};printf("%d\\n",total(arr,3));return 0;}""")

# array index from nested expression
e("po_nested_idx","""
int main(void){int a[16];for(int i=0;i<16;i++)a[i]=i;int s=0;
for(int i=0;i<4;i++)for(int j=0;j<4;j++)s+=a[i*4+j]*((i+j)%2);printf("%d\\n",s);return 0;}""")

# bitfield emulation via masks
e("po_bitmask","""
int main(void){unsigned packed=0;packed|=(5<<0);packed|=(3<<4);packed|=(7<<8);
int a=packed&0xF,b=(packed>>4)&0xF,c=(packed>>8)&0xF;printf("%d %d %d\\n",a,b,c);return 0;}""")

# 2D malloc with computed total
e("po_2d_flat","""
int main(void){int R=3,C=4;int*g=malloc(sizeof(int)*R*C);
for(int i=0;i<R;i++)for(int j=0;j<C;j++)g[i*C+j]=i*C+j;
int s=0;for(int i=0;i<R*C;i++)s+=g[i];free(g);printf("%d\\n",s);return 0;}""")

# char* array iteration
e("po_charptr_arr","""
int main(void){const char*words[3]={"cat","dog","bird"};int total=0;
for(int i=0;i<3;i++)for(int j=0;words[i][j];j++)total++;printf("%d\\n",total);return 0;}""")

# accumulate via function with state pointer
e("po_acc_state","""
void acc(int*sum,int*cnt,int v){*sum+=v;*cnt+=1;}
int main(void){int sum=0,cnt=0;for(int i=1;i<=10;i++)acc(&sum,&cnt,i);printf("%d %d\\n",sum,cnt);return 0;}""")

# conditional with assignment side effect
e("po_cond_assign","""
int main(void){int a[5]={5,0,3,0,8};int last=0,s=0;for(int i=0;i<5;i++){if(a[i])last=a[i];s+=last;}printf("%d %d\\n",s,last);return 0;}""")

# recursive power
e("po_power","""
int ipow(int b,int e){if(e==0)return 1;return b*ipow(b,e-1);}
int main(void){printf("%d %d %d\\n",ipow(2,10),ipow(3,4),ipow(5,0));return 0;}""")

# swap via pointers in array
e("po_swap_arr","""
void swap(int*a,int*b){int t=*a;*a=*b;*b=t;}
int main(void){int a[6]={6,5,4,3,2,1};for(int i=0;i<3;i++)swap(&a[i],&a[5-i]);
int s=0;for(int i=0;i<6;i++)s+=a[i]*(i+1);printf("%d\\n",s);return 0;}""")

print(f"generated {n} files")
