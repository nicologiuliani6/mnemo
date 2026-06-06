#!/usr/bin/env python3
"""Batch 13: string ops, malloc/free patterns, enum/const, FSM, ptr edge,
   ternary lvalue-ish, nested arrays of ptr, recursion tree, modular arith."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# strncpy-like manual + length
e("pd_strncpy","""
int main(void){char src[]="hello world";char dst[6];int i;for(i=0;i<5&&src[i];i++)dst[i]=src[i];dst[i]=0;printf("%s %d\\n",dst,i);return 0;}""")

# malloc, write, realloc-free pattern (grow once outside loop)
e("pd_malloc_grow","""
int main(void){int*a=malloc(sizeof(int)*4);for(int i=0;i<4;i++)a[i]=i*i;
int*b=malloc(sizeof(int)*8);for(int i=0;i<4;i++)b[i]=a[i];for(int i=4;i<8;i++)b[i]=i*i;free(a);
int s=0;for(int i=0;i<8;i++)s+=b[i];printf("%d\\n",s);free(b);return 0;}""")

# enum + const arithmetic
e("pd_enum_const","""
enum{KB=1024,MB=KB*1024};
int main(void){const int x=KB*4;const int y=MB/512;printf("%d %d %d\\n",KB,MB,x+y);return 0;}""")

# FSM: parse simple number with sign
e("pd_fsm_parse","""
int main(void){const char*s="-42";int sign=1,i=0,val=0;
if(s[i]=='-'){sign=-1;i++;}else if(s[i]=='+')i++;
while(s[i]>='0'&&s[i]<='9'){val=val*10+(s[i]-'0');i++;}
printf("%d\\n",sign*val);return 0;}""")

# pointer arithmetic edge: end pointer, p==q
e("pd_ptr_end","""
int main(void){int a[5]={1,2,3,4,5};int*p=a;int*end=a+5;int s=0;while(p!=end)s+=*p++;
printf("%d %d\\n",s,(int)(end-a));return 0;}""")

# ternary selecting array element
e("pd_ternary_idx","""
int main(void){int a[2][3]={{1,2,3},{4,5,6}};int s=0;
for(int i=0;i<6;i++)s+=a[i<3?0:1][i%3];printf("%d\\n",s);return 0;}""")

# recursion: tree node count via array
e("pd_tree_count","""
struct N{int l,r;};struct N t[7]={{1,2},{3,4},{5,6},{-1,-1},{-1,-1},{-1,-1},{-1,-1}};
int cnt(int i){if(i<0)return 0;return 1+cnt(t[i].l)+cnt(t[i].r);}
int main(void){printf("%d\\n",cnt(0));return 0;}""")

# modular exponentiation
e("pd_modexp","""
int modexp(int b,int e,int m){int r=1;b%=m;while(e>0){if(e&1)r=(r*b)%m;e>>=1;b=(b*b)%m;}return r;}
int main(void){printf("%d %d %d\\n",modexp(3,5,7),modexp(2,10,1000),modexp(7,4,13));return 0;}""")

# array of pointers to functions, dispatch by computed index
e("pd_fn_dispatch","""
int f0(int x){return x;}int f1(int x){return x+1;}int f2(int x){return x*2;}
int main(void){int(*fns[3])(int)={f0,f1,f2};int v=5;for(int i=0;i<6;i++)v=fns[i%3](v);printf("%d\\n",v);return 0;}""")

# struct copy via assignment in loop
e("pd_struct_copy_loop","""
struct P{int x,y;};
int main(void){struct P a[4]={{1,1},{2,4},{3,9},{4,16}};struct P b[4];
for(int i=0;i<4;i++)b[i]=a[3-i];int s=0;for(int i=0;i<4;i++)s+=b[i].x*10+b[i].y;printf("%d\\n",s);return 0;}""")

# nested switch
e("pd_nested_switch","""
int main(void){int r=0;for(int a=0;a<3;a++)for(int b=0;b<3;b++){switch(a){case 0:switch(b){case 0:r+=1;break;default:r+=2;}break;case 1:r+=10;break;default:r+=100;}}printf("%d\\n",r);return 0;}""")

# long arithmetic
e("pd_long_arith","""
int main(void){long a=1000000;long b=a*a;printf("%ld\\n",b/1000);return 0;}""")

# char digit sum
e("pd_digitsum","""
int main(void){const char*s="9876543210";int sum=0;for(int i=0;s[i];i++)sum+=s[i]-'0';printf("%d\\n",sum);return 0;}""")

# bit reversal
e("pd_bitrev","""
unsigned rev8(unsigned x){unsigned r=0;for(int i=0;i<8;i++){r=(r<<1)|(x&1);x>>=1;}return r;}
int main(void){printf("%u %u %u\\n",rev8(1),rev8(0x80),rev8(0xAB));return 0;}""")

# accumulate min/max
e("pd_minmax","""
int main(void){int a[9]={3,7,1,9,2,8,4,6,5};int mn=a[0],mx=a[0];for(int i=1;i<9;i++){if(a[i]<mn)mn=a[i];if(a[i]>mx)mx=a[i];}printf("%d %d %d\\n",mn,mx,mx-mn);return 0;}""")

# pointer to struct array element, mutate via ptr
e("pd_struct_ptr_mut","""
struct C{int v;};
int main(void){struct C arr[4]={{10},{20},{30},{40}};struct C*p=&arr[2];p->v=99;(p-1)->v=88;
int s=0;for(int i=0;i<4;i++)s+=arr[i].v;printf("%d\\n",s);return 0;}""")

print(f"generated {n} files")
