#!/usr/bin/env python3
"""Batch 9: corner non coperti — promozioni intere, char arith, mixed sign,
   ptr arith, switch fallthrough, ternary annidati, sizeof, do-while, init."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# switch fallthrough (no break)
e("p9_switch_fall","""
int main(void){int r=0;for(int x=0;x<5;x++){switch(x){case 0:case 1:r+=1;break;case 2:r+=10;case 3:r+=100;break;default:r+=1000;}}printf("%d\\n",r);return 0;}""")

# char arithmetic + promotion
e("p9_char_arith","""
int main(void){char a='A',b='z';int d=b-a;char c=a+1;printf("%d %c %d\\n",d,c,a*2);return 0;}""")

# mixed signed/unsigned comparison
e("p9_mixed_sign","""
int main(void){int i=-1;unsigned u=1;printf("%d %d\\n",i<u,(unsigned)i>u);
unsigned a=10;int b=-5;printf("%u\\n",a+b);return 0;}""")

# pointer arithmetic: p - array, *(p+i), p[-1]
e("p9_ptr_arith","""
int main(void){int a[6]={10,20,30,40,50,60};int*p=a+3;
printf("%d %d %d %ld\\n",*p,p[-1],*(p+2),(long)(p-a));return 0;}""")

# nested ternary chain
e("p9_ternary_chain","""
int classify(int x){return x<0?-1:x==0?0:x<10?1:x<100?2:3;}
int main(void){int s=0;int v[6]={-5,0,5,50,500,9};for(int i=0;i<6;i++)s=s*10+(classify(v[i])+1);printf("%d\\n",s);return 0;}""")

# sizeof various
e("p9_sizeof","""
int main(void){int a[10];char c[7];struct S{int x;char y;}s;
printf("%zu %zu %zu %zu\\n",sizeof(int),sizeof(a),sizeof(c),sizeof a/sizeof a[0]);return 0;}""")

# do-while accumulation
e("p9_dowhile","""
int main(void){int n=12345,rev=0;do{rev=rev*10+n%10;n/=10;}while(n>0);printf("%d\\n",rev);return 0;}""")

# integer division/modulo negative
e("p9_intdiv_neg","""
int main(void){int vals[4]={-17,17,-17,17},divs[4]={5,-5,-5,5};
for(int i=0;i<4;i++)printf("%d %d\\n",vals[i]/divs[i],vals[i]%divs[i]);return 0;}""")

# bit manipulation: set/clear/toggle/test bit
e("p9_bitops","""
int main(void){unsigned x=0;x|=(1u<<3);x|=(1u<<7);x&=~(1u<<3);x^=(1u<<5);
printf("%u %d %d\\n",x,(x>>7)&1,(x>>3)&1);return 0;}""")

# array of structs init + mutate
e("p9_struct_arr_mut","""
struct P{int x,y;};
int main(void){struct P a[4];for(int i=0;i<4;i++){a[i].x=i;a[i].y=i*i;}
int s=0;for(int i=0;i<4;i++){a[i].x+=a[i].y;s+=a[i].x;}printf("%d\\n",s);return 0;}""")

# 2D array row/col sums
e("p9_2d_sums","""
int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;
int rs=0,cs=0;for(int j=0;j<4;j++)cs+=m[1][j];for(int i=0;i<3;i++)rs+=m[i][2];
printf("%d %d\\n",rs,cs);return 0;}""")

# function returning pointer into array
e("p9_ret_ptr","""
static int* maxptr(int*a,int n){int*m=a;for(int i=1;i<n;i++)if(a[i]>*m)m=a+i;return m;}
int main(void){int a[7]={3,1,4,1,5,9,2};int*p=maxptr(a,7);printf("%d %ld\\n",*p,(long)(p-a));return 0;}""")

# string: reverse in place
e("p9_str_reverse","""
int main(void){char s[]="reversed";int n=0;while(s[n])n++;
for(int i=0,j=n-1;i<j;i++,j--){char t=s[i];s[i]=s[j];s[j]=t;}printf("%s\\n",s);return 0;}""")

# recursion: ackermann (small)
e("p9_ackermann","""
int ack(int m,int nn){if(m==0)return nn+1;if(nn==0)return ack(m-1,1);return ack(m-1,ack(m,nn-1));}
int main(void){printf("%d %d %d\\n",ack(2,3),ack(3,3),ack(1,5));return 0;}""")

# compound assignment chain on array element
e("p9_arr_compound","""
int main(void){int a[5]={1,2,3,4,5};a[2]+=a[0];a[2]*=a[1];a[2]-=a[3];a[2]<<=1;
int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d %d\\n",a[2],s);return 0;}""")

# global counter mutated across functions
e("p9_global_mut","""
int g=100;
void inc(int d){g+=d;}
int get(void){return g;}
int main(void){for(int i=1;i<=5;i++)inc(i);printf("%d %d\\n",get(),g);return 0;}""")

# unsigned overflow + cast roundtrip
e("p9_ucast","""
int main(void){unsigned char b=200;b+=100;int i=b;unsigned u=0xFFFFFFFFu;int si=(int)u;
printf("%d %u %d\\n",i,u,si);return 0;}""")

# multi-return via pointers
e("p9_multiret","""
void divmod(int a,int b,int*q,int*r){*q=a/b;*r=a%b;}
int main(void){int q,r;divmod(47,5,&q,&r);printf("%d %d\\n",q,r);return 0;}""")

print(f"generated {n} files")
