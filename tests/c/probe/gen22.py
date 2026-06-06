#!/usr/bin/env python3
"""Batch 22: mutual recursion, whole-struct assign, printf widths, computed idx,
   multi-break, goto-free FSM, ptr-to-struct-array, accumulate patterns."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# mutual recursion even/odd
e("pm_mutual","""
int is_even(int n);int is_odd(int n){return n==0?0:is_even(n-1);}
int is_even(int n){return n==0?1:is_odd(n-1);}
int main(void){printf("%d %d %d\\n",is_even(10),is_odd(7),is_even(0));return 0;}""")

# whole struct assignment
e("pm_struct_assign","""
struct P{int x,y,z;};
int main(void){struct P a={1,2,3};struct P b;b=a;b.x=10;printf("%d %d %d %d\\n",a.x,b.x,b.y,b.z);return 0;}""")

# printf %ld %u edge
e("pm_printf_width","""
int main(void){long a=123456789;unsigned b=3000000000u;printf("%ld %u\\n",a,b);return 0;}""")

# computed multi index
e("pm_computed_idx","""
int main(void){int a[20];for(int i=0;i<20;i++)a[i]=i;int s=0;
for(int i=0;i<5;i++)s+=a[i*4]+a[i*4+1];printf("%d\\n",s);return 0;}""")

# multiple break levels via flag
e("pm_multibreak","""
int main(void){int found=0,fi=0,fj=0;int m[5][5];for(int i=0;i<5;i++)for(int j=0;j<5;j++)m[i][j]=i*5+j;
for(int i=0;i<5&&!found;i++)for(int j=0;j<5;j++){if(m[i][j]==13){found=1;fi=i;fj=j;break;}}
printf("%d %d %d\\n",found,fi,fj);return 0;}""")

# goto-free state machine
e("pm_fsm","""
int main(void){const char*in="aabbbc";int state=0,acc=0;
for(int i=0;in[i];i++){char c=in[i];
if(state==0){if(c=='a')acc+=1;else state=1;}
if(state==1){if(c=='b')acc+=10;else state=2;}
if(state==2){acc+=100;}}printf("%d\\n",acc);return 0;}""")

# pointer to struct array
e("pm_ptr_struct_arr","""
struct R{int v;};
int main(void){struct R arr[5]={{1},{2},{3},{4},{5}};struct R*p=arr;int s=0;
for(int i=0;i<5;i++)s+=(p+i)->v;printf("%d\\n",s);return 0;}""")

# accumulate with early continue
e("pm_continue","""
int main(void){int s=0;for(int i=1;i<=20;i++){if(i%3==0)continue;if(i%5==0)continue;s+=i;}printf("%d\\n",s);return 0;}""")

# nested ternary deep
e("pm_deep_ternary","""
int classify(int x){return x<0?-1:x==0?0:x<10?1:x<100?2:3;}
int main(void){int t=0;int v[6]={-5,0,7,50,200,9};for(int i=0;i<6;i++)t=t*10+(classify(v[i])+1);printf("%d\\n",t);return 0;}""")

# array sum with pointer walk and sentinel
e("pm_sentinel","""
int main(void){int a[8]={3,1,4,1,5,9,-1,2};int s=0;int*p=a;while(*p!=-1){s+=*p;p++;}printf("%d\\n",s);return 0;}""")

print(f"generated {n} files")
