#!/usr/bin/env python3
"""Batch 11: corner avanzati — ptr-to-array param, array-of-array passing,
   comma in for, multiple returns, const params, deep recursion, 2D malloc,
   struct ptr in array, switch-return-default, nested calls."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# pointer to array param: int (*p)[4]
e("pb_ptr_to_array","""
int sumrow(int(*row)[4],int i){int s=0;for(int j=0;j<4;j++)s+=row[i][j];return s;}
int main(void){int m[3][4]={{1,2,3,4},{5,6,7,8},{9,10,11,12}};
printf("%d %d %d\\n",sumrow(m,0),sumrow(m,1),sumrow(m,2));return 0;}""")

# 2D array passed to function
e("pb_2d_param","""
int diag(int m[4][4]){int s=0;for(int i=0;i<4;i++)s+=m[i][i];return s;}
int main(void){int m[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;printf("%d\\n",diag(m));return 0;}""")

# comma operator in for
e("pb_comma_for","""
int main(void){int s=0;for(int i=0,j=10;i<j;i++,j--)s+=i*j;printf("%d\\n",s);return 0;}""")

# multiple return paths
e("pb_multiret_paths","""
int sign3(int x){if(x>5)return 2;if(x>0)return 1;if(x==0)return 0;return -1;}
int main(void){int s=0;for(int i=-2;i<=8;i++)s=s*10+(sign3(i)+2);printf("%d\\n",s);return 0;}""")

# deep recursion: sum to n
e("pb_deep_rec","""
int sumto(int n){if(n<=0)return 0;return n+sumto(n-1);}
int main(void){printf("%d %d\\n",sumto(100),sumto(50));return 0;}""")

# 2D malloc flat
e("pb_2d_malloc","""
int main(void){int R=4,C=5;int*g=malloc(sizeof(int)*R*C);
for(int i=0;i<R;i++)for(int j=0;j<C;j++)g[i*C+j]=(i+1)*(j+1);
int s=0;for(int i=0;i<R*C;i++)s+=g[i];printf("%d\\n",s);free(g);return 0;}""")

# switch with return + trailing default
e("pb_switch_default","""
int weekday(int d){switch(d){case 0:return 7;case 6:return 6;}return d;}
int main(void){int s=0;for(int i=0;i<7;i++)s=s*10+weekday(i);printf("%d\\n",s);return 0;}""")

# nested function calls
e("pb_nested_calls","""
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int main(void){printf("%d\\n",add(mul(2,3),mul(add(1,2),4)));return 0;}""")

# const pointer param
e("pb_const_param","""
int count_pos(const int*a,int n){int c=0;for(int i=0;i<n;i++)if(a[i]>0)c++;return c;}
int main(void){int a[8]={-1,2,-3,4,5,-6,7,8};printf("%d\\n",count_pos(a,8));return 0;}""")

# struct passed by value, modified locally
e("pb_struct_byval","""
struct V{int a,b,c;};
int sum(struct V v){v.a+=10;return v.a+v.b+v.c;}
int main(void){struct V x={1,2,3};int r=sum(x);printf("%d %d %d %d\\n",r,x.a,x.b,x.c);return 0;}""")

# array of struct pointers (indices)
e("pb_graph","""
struct Node{int val,next;};
int main(void){struct Node g[5]={{10,1},{20,2},{30,3},{40,4},{50,-1}};
int s=0,cur=0;while(cur!=-1){s+=g[cur].val;cur=g[cur].next;}printf("%d\\n",s);return 0;}""")

# binary search
e("pb_bsearch","""
int bs(int*a,int n,int key){int lo=0,hi=n-1;while(lo<=hi){int mid=(lo+hi)/2;if(a[mid]==key)return mid;if(a[mid]<key)lo=mid+1;else hi=mid-1;}return -1;}
int main(void){int a[10]={1,3,5,7,9,11,13,15,17,19};printf("%d %d %d\\n",bs(a,10,7),bs(a,10,19),bs(a,10,8));return 0;}""")

# GCD via subtraction
e("pb_gcd_sub","""
int gcd(int a,int b){while(a!=b){if(a>b)a-=b;else b-=a;}return a;}
int main(void){printf("%d %d %d\\n",gcd(48,36),gcd(17,5),gcd(100,75));return 0;}""")

# nested loops with break/continue
e("pb_break_cont","""
int main(void){int found=0,fi=0,fj=0;for(int i=0;i<10;i++){for(int j=0;j<10;j++){if(i*j==12){found=1;fi=i;fj=j;break;}}if(found)break;}
printf("%d %d %d\\n",found,fi,fj);return 0;}""")

# pointer increment through string
e("pb_str_walk","""
int main(void){char s[]="abcABC123";int la=0,ua=0,di=0;for(char*p=s;*p;++p){if(*p>='a'&&*p<='z')la++;else if(*p>='A'&&*p<='Z')ua++;else di++;}printf("%d %d %d\\n",la,ua,di);return 0;}""")

# accumulate via function returning struct
e("pb_ret_struct","""
struct Pair{int sum,prod;};
struct Pair compute(int a,int b){struct Pair p;p.sum=a+b;p.prod=a*b;return p;}
int main(void){struct Pair r=compute(7,6);printf("%d %d\\n",r.sum,r.prod);return 0;}""")

print(f"generated {n} files")
