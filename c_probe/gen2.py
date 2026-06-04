#!/usr/bin/env python3
"""Batch 2: deep memory / pointers / structs / argument passing edge cases."""
import os
OUT = os.path.join(os.path.dirname(__file__), "t")
os.makedirs(OUT, exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
def emit(name, body, h=H):
    global n; n+=1
    open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# ---- POINTERS deep ----
emit("p_arr_decay_fn","""
int first(int*p){return *p;}
int main(void){int a[3]={9,8,7};printf("%d\\n",first(a));printf("%d\\n",first(a+1));return 0;}""")
emit("p_2d_rowptr","""
int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;int(*r)[4]=m;printf("%d %d\\n",r[1][2],(*(r+2))[3]);return 0;}""")
emit("p_charptr_walk","""
int main(void){char*s="hello";int n=0;while(*s){n++;s++;}printf("%d\\n",n);return 0;}""")
emit("p_ptr_compare","""
int main(void){int a[5];int*p=&a[1];int*q=&a[3];printf("%d %d %d\\n",p<q,p>q,p==q);return 0;}""")
emit("p_double_deref_write","""
void setp(int**pp,int*target){*pp=target;}
int main(void){int x=0;int*p;setp(&p,&x);*p=77;printf("%d\\n",x);return 0;}""")
emit("p_arr_of_ptr_sort","""
int main(void){int a=3,b=1,c=2;int*p[3]={&a,&b,&c};for(int i=0;i<3;i++)for(int j=i+1;j<3;j++)if(*p[i]>*p[j]){int*t=p[i];p[i]=p[j];p[j]=t;}printf("%d %d %d\\n",*p[0],*p[1],*p[2]);return 0;}""")
emit("p_ret_ptr_to_static","""
int*getbuf(void){static int b[3]={11,22,33};return b;}
int main(void){int*p=getbuf();printf("%d %d %d\\n",p[0],p[1],p[2]);return 0;}""")
emit("p_ptr_param_array_write","""
void fill(int*a,int n,int v){for(int i=0;i<n;i++)a[i]=v+i;}
int main(void){int a[5];fill(a,5,100);int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d\\n",s);return 0;}""")
emit("p_string_copy_manual","""
int main(void){char src[]="abc";char dst[4];for(int i=0;i<4;i++)dst[i]=src[i];printf("%s\\n",dst);return 0;}""")
emit("p_offset_struct","""
struct P{int a;int b;int c;};
int main(void){struct P p={1,2,3};int*ip=&p.b;*ip=99;printf("%d %d %d\\n",p.a,p.b,p.c);return 0;}""")

# ---- ARRAYS deep ----
emit("a_2d_transpose","""
int main(void){int m[2][2]={{1,2},{3,4}};for(int i=0;i<2;i++)for(int j=i+1;j<2;j++){int t=m[i][j];m[i][j]=m[j][i];m[j][i]=t;}printf("%d %d %d %d\\n",m[0][0],m[0][1],m[1][0],m[1][1]);return 0;}""")
emit("a_init_designated","""
int main(void){int a[5]={[0]=1,[4]=5,[2]=3};for(int i=0;i<5;i++)printf("%d",a[i]);printf("\\n");return 0;}""")
emit("a_string_array","""
int main(void){const char*days[3]={"mon","tue","wed"};for(int i=0;i<3;i++)printf("%s ",days[i]);printf("\\n");return 0;}""")
emit("a_2d_init_flat","""
int main(void){int a[2][3]={1,2,3,4,5,6};printf("%d %d\\n",a[0][2],a[1][0]);return 0;}""")
emit("a_partial_struct","""
struct P{int x;int y;};
int main(void){struct P a[3]={{1,2}};printf("%d %d %d %d\\n",a[0].x,a[0].y,a[1].x,a[2].y);return 0;}""")
emit("a_bubble","""
int main(void){int a[6]={5,2,8,1,9,3};for(int i=0;i<6;i++)for(int j=0;j<5-i;j++)if(a[j]>a[j+1]){int t=a[j];a[j]=a[j+1];a[j+1]=t;}for(int i=0;i<6;i++)printf("%d",a[i]);printf("\\n");return 0;}""")

# ---- STRUCTS deep ----
emit("s_array_in_struct","""
struct V{int data[4];int len;};
int main(void){struct V v;v.len=4;for(int i=0;i<4;i++)v.data[i]=i*10;int s=0;for(int i=0;i<v.len;i++)s+=v.data[i];printf("%d\\n",s);return 0;}""")
emit("s_ptr_in_struct","""
struct Box{int*p;};
int main(void){int x=42;struct Box b;b.p=&x;*b.p=100;printf("%d\\n",x);return 0;}""")
emit("s_nested_deep","""
struct A{int v;};struct B{struct A a;};struct C{struct B b;};
int main(void){struct C c;c.b.a.v=7;printf("%d\\n",c.b.a.v);return 0;}""")
emit("s_copy_assign","""
struct P{int x;int y;};
int main(void){struct P a={1,2};struct P b=a;b.x=99;printf("%d %d %d %d\\n",a.x,a.y,b.x,b.y);return 0;}""")
emit("s_return_modify","""
struct P{int x;int y;};
struct P scale(struct P p,int f){p.x*=f;p.y*=f;return p;}
int main(void){struct P p={2,3};struct P q=scale(p,4);printf("%d %d %d %d\\n",p.x,p.y,q.x,q.y);return 0;}""")
emit("s_arr_of_struct_fn","""
struct P{int x;int y;};
int sumall(struct P*a,int n){int s=0;for(int i=0;i<n;i++)s+=a[i].x+a[i].y;return s;}
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};printf("%d\\n",sumall(a,3));return 0;}""")
emit("s_struct_in_array_mut","""
struct P{int x;};
int main(void){struct P a[4];for(int i=0;i<4;i++)a[i].x=i;for(int i=0;i<4;i++)a[i].x*=a[i].x;printf("%d %d %d %d\\n",a[0].x,a[1].x,a[2].x,a[3].x);return 0;}""")
emit("s_union_in_struct","""
union U{int i;char c;};
struct S{union U u;int tag;};
int main(void){struct S s;s.u.i=300;s.tag=1;printf("%d %d\\n",s.u.i,s.tag);return 0;}""")
emit("s_anon_struct","""
struct{int x;int y;}p={5,6};
int main(void){printf("%d\\n",p.x+p.y);return 0;}""")
emit("s_bitops_field","""
struct Flags{int a;int b;};
int main(void){struct Flags f={0xF0,0x0F};printf("%d %d\\n",f.a|f.b,f.a&f.b);return 0;}""")

# ---- PASSING / RECURSION deep ----
emit("pass_fib_rec","""
int fib(int n){return n<2?n:fib(n-1)+fib(n-2);}
int main(void){for(int i=0;i<10;i++)printf("%d ",fib(i));printf("\\n");return 0;}""")
emit("pass_ackermann_small","""
int ack(int m,int n){if(m==0)return n+1;if(n==0)return ack(m-1,1);return ack(m-1,ack(m,n-1));}
int main(void){printf("%d\\n",ack(2,3));return 0;}""")
emit("pass_ptr_swap_struct","""
struct P{int x;int y;};
void swap(struct P*a,struct P*b){struct P t=*a;*a=*b;*b=t;}
int main(void){struct P a={1,2},b={3,4};swap(&a,&b);printf("%d %d %d %d\\n",a.x,a.y,b.x,b.y);return 0;}""")
emit("pass_array_2d_modify","""
void inc2d(int m[2][2]){for(int i=0;i<2;i++)for(int j=0;j<2;j++)m[i][j]++;}
int main(void){int m[2][2]={{1,2},{3,4}};inc2d(m);printf("%d %d %d %d\\n",m[0][0],m[0][1],m[1][0],m[1][1]);return 0;}""")
emit("pass_count_param","""
void count(int n,int*out){*out=0;for(int i=1;i<=n;i++)*out+=i;}
int main(void){int r;count(10,&r);printf("%d\\n",r);return 0;}""")
emit("pass_deep_recursion","""
int sum_to(int n){if(n==0)return 0;return n+sum_to(n-1);}
int main(void){printf("%d\\n",sum_to(100));return 0;}""")
emit("pass_gcd","""
int gcd(int a,int b){while(b){int t=b;b=a%b;a=t;}return a;}
int main(void){printf("%d %d\\n",gcd(48,36),gcd(17,5));return 0;}""")

# ---- MEMORY / malloc deep ----
emit("m_malloc_array_fill","""
int main(void){int n=10;int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i*i;int s=0;for(int i=0;i<n;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")
emit("m_malloc_2blocks","""
int main(void){int*a=malloc(sizeof(int)*3);int*b=malloc(sizeof(int)*3);for(int i=0;i<3;i++){a[i]=i;b[i]=i*10;}printf("%d %d\\n",a[2],b[2]);free(a);free(b);return 0;}""")
emit("m_malloc_struct_arr","""
struct P{int x;int y;};
int main(void){struct P*a=malloc(sizeof(struct P)*3);for(int i=0;i<3;i++){a[i].x=i;a[i].y=i*2;}int s=0;for(int i=0;i<3;i++)s+=a[i].x+a[i].y;printf("%d\\n",s);free(a);return 0;}""")
emit("m_calloc_like","""
int main(void){int*a=malloc(sizeof(int)*5);for(int i=0;i<5;i++)a[i]=0;a[2]=7;int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")
emit("m_ptr_into_malloc","""
int main(void){int*a=malloc(sizeof(int)*4);int*p=a+2;*p=99;printf("%d\\n",a[2]);free(a);return 0;}""")

# ---- MIXED edge ----
emit("mix_matrix_mul","""
int main(void){int a[2][2]={{1,2},{3,4}};int b[2][2]={{5,6},{7,8}};int c[2][2]={{0,0},{0,0}};for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)c[i][j]+=a[i][k]*b[k][j];printf("%d %d %d %d\\n",c[0][0],c[0][1],c[1][0],c[1][1]);return 0;}""")
emit("mix_linked_arr","""
struct N{int val;int next;};
int main(void){struct N pool[5];for(int i=0;i<5;i++){pool[i].val=(i+1)*10;pool[i].next=i+1;}pool[4].next=-1;int cur=0,sum=0;while(cur!=-1){sum+=pool[cur].val;cur=pool[cur].next;}printf("%d\\n",sum);return 0;}""")
emit("mix_stack_struct","""
struct Stack{int data[10];int top;};
int main(void){struct Stack s;s.top=0;for(int i=0;i<5;i++){s.data[s.top]=i*i;s.top++;}int sum=0;while(s.top>0){s.top--;sum+=s.data[s.top];}printf("%d\\n",sum);return 0;}""")
emit("mix_count_chars","""
int main(void){char*s="hello world";int v=0;for(int i=0;s[i];i++)if(s[i]=='o')v++;printf("%d\\n",v);return 0;}""")
emit("mix_2d_ptr_arith","""
int main(void){int m[3][3];int*p=&m[0][0];for(int i=0;i<9;i++)p[i]=i;printf("%d %d %d\\n",m[0][0],m[1][1],m[2][2]);return 0;}""")
emit("mix_enum_switch","""
enum Op{ADD,SUB,MUL};
int apply(enum Op o,int a,int b){switch(o){case ADD:return a+b;case SUB:return a-b;case MUL:return a*b;}return 0;}
int main(void){printf("%d %d %d\\n",apply(ADD,6,3),apply(SUB,6,3),apply(MUL,6,3));return 0;}""")
emit("mix_const_arr","""
int main(void){const int a[3]={10,20,30};int s=0;for(int i=0;i<3;i++)s+=a[i];printf("%d\\n",s);return 0;}""")
emit("mix_nested_loop_sum","""
int main(void){int total=0;for(int i=1;i<=5;i++)for(int j=1;j<=5;j++)total+=i*j;printf("%d\\n",total);return 0;}""")

print(f"generated {n} files")
