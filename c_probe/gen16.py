#!/usr/bin/env python3
"""Batch 16: malloc corners post nblk-fix — calloc runtime, 3D ptr, realloc-grow,
   struct-ptr in malloc, ptr-of-ptr reassign, fn-ptr in struct, mixed."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# calloc with runtime count
e("pg_calloc_rt","""
int main(void){int n=5;int*a=calloc(n,sizeof(int));int s=0;for(int i=0;i<n;i++)s+=a[i];
for(int i=0;i<n;i++)a[i]=i*3;for(int i=0;i<n;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")

# two interleaved malloc same loop body, runtime size
e("pg_interleave","""
int main(void){int n=4;int*a=malloc(sizeof(int)*n);int*b=malloc(sizeof(int)*n);
for(int i=0;i<n;i++){a[i]=i;b[i]=i*i;}int s=0;for(int i=0;i<n;i++)s+=a[i]+b[i];printf("%d\\n",s);
free(a);free(b);return 0;}""")

# 3D-ish: array of arrays of ptr
e("pg_jagged","""
int main(void){int R=3;int**g=malloc(sizeof(int*)*R);int len[3]={2,3,4};
for(int i=0;i<R;i++){g[i]=malloc(sizeof(int)*len[i]);for(int j=0;j<len[i];j++)g[i][j]=i*10+j;}
int s=0;for(int i=0;i<R;i++)for(int j=0;j<len[i];j++)s+=g[i][j];
for(int i=0;i<R;i++)free(g[i]);free(g);printf("%d\\n",s);return 0;}""")

# struct ptr via malloc, runtime count, field writes
e("pg_struct_malloc","""
struct P{int a,b,c;};
int main(void){int n=4;struct P*p=malloc(sizeof(struct P)*n);
for(int i=0;i<n;i++){p[i].a=i;p[i].b=i*2;p[i].c=i*3;}
int s=0;for(int i=0;i<n;i++)s+=p[i].a+p[i].b+p[i].c;printf("%d\\n",s);free(p);return 0;}""")

# pointer-of-pointer reassign mid-loop
e("pg_ptr_reassign","""
int main(void){int n=3;int*a=malloc(sizeof(int)*n);int*b=malloc(sizeof(int)*n);
for(int i=0;i<n;i++){a[i]=i+1;b[i]=(i+1)*10;}int*p=a;int s=0;
for(int k=0;k<2;k++){for(int i=0;i<n;i++)s+=p[i];p=b;}printf("%d\\n",s);free(a);free(b);return 0;}""")

# malloc, write via pointer arithmetic *(p+i)
e("pg_ptr_arith_write","""
int main(void){int n=6;int*p=malloc(sizeof(int)*n);for(int i=0;i<n;i++)*(p+i)=i*i;
int s=0;for(int i=0;i<n;i++)s+=*(p+i);printf("%d\\n",s);free(p);return 0;}""")

# grow pattern: alloc small, alloc big, copy
e("pg_grow","""
int main(void){int n=4;int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i+1;
int m=8;int*b=malloc(sizeof(int)*m);for(int i=0;i<n;i++)b[i]=a[i];for(int i=n;i<m;i++)b[i]=i+1;
free(a);int s=0;for(int i=0;i<m;i++)s+=b[i];free(b);printf("%d\\n",s);return 0;}""")

# nested malloc in nested loop, both runtime
e("pg_nested_loop_malloc","""
int main(void){int R=4,C=3;int**g=malloc(sizeof(int*)*R);
for(int i=0;i<R;i++){g[i]=malloc(sizeof(int)*C);for(int j=0;j<C;j++)g[i][j]=(i+1)*(j+1);}
int s=0;for(int i=0;i<R;i++)for(int j=0;j<C;j++)s+=g[i][j];
for(int i=0;i<R;i++)free(g[i]);free(g);printf("%d\\n",s);return 0;}""")

# malloc count from function return
e("pg_malloc_fncount","""
int sz(void){return 7;}
int main(void){int n=sz();int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i;
int s=0;for(int i=0;i<n;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")

# malloc with expression count (n+1)
e("pg_malloc_expr","""
int main(void){int n=5;int*a=malloc(sizeof(int)*(n+1));for(int i=0;i<=n;i++)a[i]=i*2;
int s=0;for(int i=0;i<=n;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")

print(f"generated {n} files")
