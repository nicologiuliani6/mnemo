#!/usr/bin/env python3
"""Batch 14: compound literal, array-of-strings, 2D char table, struct-with-array
   byval, 2D malloc via ptr-array, fn-ptr compare, string concat, nested init."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# array of string literals
e("pe_str_array","""
int main(void){const char*days[3]={"Mon","Tue","Wed"};int s=0;
for(int i=0;i<3;i++)for(int j=0;days[i][j];j++)s+=days[i][j];printf("%d\\n",s);return 0;}""")

# 2D char array (string table)
e("pe_char_table","""
int main(void){char names[3][8]={"alice","bob","carol"};int s=0;
for(int i=0;i<3;i++){int j=0;while(names[i][j]){s+=names[i][j];j++;}}printf("%d\\n",s);return 0;}""")

# struct with array field passed by value
e("pe_struct_arr_byval","""
struct Vec{int d[4];};
int dot(struct Vec a,struct Vec b){int s=0;for(int i=0;i<4;i++)s+=a.d[i]*b.d[i];return s;}
int main(void){struct Vec u={{1,2,3,4}},v={{5,6,7,8}};printf("%d\\n",dot(u,v));return 0;}""")

# 2D malloc via array of pointers
e("pe_2d_ptrarr","""
int main(void){int R=3,C=4;int**g=malloc(sizeof(int*)*R);for(int i=0;i<R;i++){g[i]=malloc(sizeof(int)*C);for(int j=0;j<C;j++)g[i][j]=i*C+j;}
int s=0;for(int i=0;i<R;i++)for(int j=0;j<C;j++)s+=g[i][j];for(int i=0;i<R;i++)free(g[i]);free(g);printf("%d\\n",s);return 0;}""")

# function pointer comparison
e("pe_fnptr_cmp","""
int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int main(void){int(*f)(int,int)=add;int eq=(f==add);int ne=(f!=sub);printf("%d %d %d\\n",eq,ne,f(3,2));return 0;}""")

# manual string concat into buffer
e("pe_strcat","""
int main(void){char buf[20];const char*a="foo",*b="bar";int k=0;
for(int i=0;a[i];i++)buf[k++]=a[i];for(int i=0;b[i];i++)buf[k++]=b[i];buf[k]=0;
printf("%s %d\\n",buf,k);return 0;}""")

# nested struct init with mixed
e("pe_nested_init","""
struct Inner{int a,b;};struct Outer{struct Inner i;int arr[3];int z;};
int main(void){struct Outer o={{1,2},{3,4,5},6};printf("%d %d %d %d %d %d\\n",o.i.a,o.i.b,o.arr[0],o.arr[1],o.arr[2],o.z);return 0;}""")

# compound assignment with array index expression
e("pe_arr_idx_expr","""
int main(void){int a[10]={0};for(int i=0;i<20;i++)a[i%10]+=i;int s=0;for(int i=0;i<10;i++)s+=a[i];printf("%d %d\\n",a[0],s);return 0;}""")

# recursive flood/depth
e("pe_depth","""
int depth(int n,int d){if(n<=1)return d;if(n%2==0)return depth(n/2,d+1);return depth(3*n+1,d+1);}
int main(void){printf("%d %d %d\\n",depth(27,0),depth(7,0),depth(1,0));return 0;}""")

# pointer to const, read-only walk
e("pe_const_walk","""
int sum_until(const int*p,int sentinel){int s=0;while(*p!=sentinel){s+=*p;p++;}return s;}
int main(void){int a[6]={5,10,15,-1,99,99};printf("%d\\n",sum_until(a,-1));return 0;}""")

# multi-dim with negative-ish index math
e("pe_md_indexmath","""
int main(void){int m[5][5];for(int i=0;i<5;i++)for(int j=0;j<5;j++)m[i][j]=(i-j)*(i-j);
int s=0;for(int i=0;i<5;i++)for(int j=0;j<5;j++)if((i+j)%2==0)s+=m[i][j];printf("%d\\n",s);return 0;}""")

# enum as array size and index
e("pe_enum_dim","""
enum{N=5};
int main(void){int a[N];for(int i=0;i<N;i++)a[i]=i*i;int s=0;for(enum{} ;0;);for(int i=0;i<N;i++)s+=a[i];printf("%d\\n",s);return 0;}""")

# unsigned comparison wraparound
e("pe_unsigned_cmp","""
int main(void){unsigned a=5,b=10;printf("%d %d %u\\n",a-b>0,(int)(a-b)<0,a-b);return 0;}""")

# char arithmetic table (caesar cipher)
e("pe_caesar","""
int main(void){char s[]="HELLO";for(int i=0;s[i];i++)s[i]=(s[i]-'A'+3)%26+'A';printf("%s\\n",s);return 0;}""")

# struct array sort by field (insertion)
e("pe_insertion_struct","""
struct R{int k;};
int main(void){struct R a[6]={{5},{2},{8},{1},{9},{3}};
for(int i=1;i<6;i++){struct R key=a[i];int j=i-1;while(j>=0&&a[j].k>key.k){a[j+1]=a[j];j--;}a[j+1]=key;}
for(int i=0;i<6;i++)printf("%d",a[i].k);printf("\\n");return 0;}""")

# bitfield in arithmetic
e("pe_bitfield_arith","""
struct Color{unsigned r:8,g:8,b:8;};
int main(void){struct Color c={255,128,64};int lum=(c.r*30+c.g*59+c.b*11)/100;printf("%u %u %u %d\\n",c.r,c.g,c.b,lum);return 0;}""")

print(f"generated {n} files")
