#!/usr/bin/env python3
"""Generate hundreds of small C programs (Mnemo subset) for gcc-vs-mnemo 1:1 diff.
Each program is deterministic, prints computed ints/strings, no float/goto/IO."""
import os, textwrap
OUT = os.path.join(os.path.dirname(__file__), "cases")
os.makedirs(OUT, exist_ok=True)
n = 0
def emit(name, body, headers="#include <stdio.h>\n"):
    global n
    n += 1
    path = os.path.join(OUT, f"{name}.c")
    with open(path, "w") as f:
        f.write(headers + body + "\n")

H_STD = "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"

# ---------- POINTERS ----------
emit("ptr_basic", """
int main(void){int x=5;int*p=&x;*p=9;printf("%d %d\\n",x,*p);return 0;}""")
emit("ptr_swap", """
void swap(int*a,int*b){int t=*a;*a=*b;*b=t;}
int main(void){int x=1,y=2;swap(&x,&y);printf("%d %d\\n",x,y);return 0;}""")
emit("ptr_multi", """
int main(void){int x=7;int*p=&x;int**pp=&p;**pp=42;printf("%d\\n",x);return 0;}""")
emit("ptr_arith_arr", """
int main(void){int a[5]={10,20,30,40,50};int*p=a;printf("%d %d %d\\n",*p,*(p+2),*(p+4));p+=3;printf("%d\\n",*p);return 0;}""")
emit("ptr_diff", """
int main(void){int a[10];int*p=&a[2];int*q=&a[7];printf("%ld\\n",(long)(q-p));return 0;}""")
emit("ptr_incdec", """
int main(void){int a[4]={1,2,3,4};int*p=a;int s=0;for(int i=0;i<4;i++){s+=*p;p++;}printf("%d\\n",s);return 0;}""")
emit("ptr_array_param", """
int sum(int*a,int n){int s=0;for(int i=0;i<n;i++)s+=a[i];return s;}
int main(void){int a[5]={1,2,3,4,5};printf("%d\\n",sum(a,5));return 0;}""")
emit("ptr_modify_arr", """
void dbl(int*a,int n){for(int i=0;i<n;i++)a[i]*=2;}
int main(void){int a[4]={1,2,3,4};dbl(a,4);printf("%d %d %d %d\\n",a[0],a[1],a[2],a[3]);return 0;}""")
emit("ptr_const", """
int main(void){const int x=5;const int*p=&x;printf("%d\\n",*p);return 0;}""")
emit("ptr_void", """
int main(void){int x=42;void*v=&x;int*p=(int*)v;printf("%d\\n",*p);return 0;}""")
emit("ptr_null_check", """
int main(void){int*p=0;if(p==0)printf("null\\n");int x=1;p=&x;if(p)printf("set %d\\n",*p);return 0;}""")
emit("ptr_star_index", """
int main(void){int a[3]={7,8,9};int*p=a;printf("%d %d\\n",p[0],p[2]);return 0;}""")
emit("ptr_to_ptr_arr", """
int main(void){int x=1,y=2,z=3;int*a[3]={&x,&y,&z};int s=0;for(int i=0;i<3;i++)s+=*a[i];printf("%d\\n",s);return 0;}""")

# ---------- ARRAYS ----------
emit("arr_2d", """
int main(void){int m[2][3]={{1,2,3},{4,5,6}};int s=0;for(int i=0;i<2;i++)for(int j=0;j<3;j++)s+=m[i][j];printf("%d\\n",s);return 0;}""")
emit("arr_2d_diag", """
int main(void){int m[3][3];for(int i=0;i<3;i++)for(int j=0;j<3;j++)m[i][j]=i*3+j;printf("%d %d %d\\n",m[0][0],m[1][1],m[2][2]);return 0;}""")
emit("arr_init_partial", """
int main(void){int a[5]={1,2};printf("%d %d %d\\n",a[0],a[1],a[2]);return 0;}""")
emit("arr_char", """
int main(void){char a[4]={'a','b','c',0};printf("%s\\n",a);return 0;}""")
emit("arr_reverse", """
int main(void){int a[5]={1,2,3,4,5};for(int i=0,j=4;i<j;i++,j--){int t=a[i];a[i]=a[j];a[j]=t;}for(int i=0;i<5;i++)printf("%d",a[i]);printf("\\n");return 0;}""")
emit("arr_2d_param", """
int sum2d(int m[2][3]){int s=0;for(int i=0;i<2;i++)for(int j=0;j<3;j++)s+=m[i][j];return s;}
int main(void){int m[2][3]={{1,2,3},{4,5,6}};printf("%d\\n",sum2d(m));return 0;}""")
emit("arr_3d", """
int main(void){int a[2][2][2];int c=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)a[i][j][k]=c++;printf("%d %d\\n",a[0][0][0],a[1][1][1]);return 0;}""")
emit("arr_sizeof", """
int main(void){int a[7];printf("%zu\\n",sizeof(a)/sizeof(a[0]));return 0;}""")

# ---------- STRUCTS ----------
emit("struct_basic", """
struct P{int x;int y;};
int main(void){struct P p={3,4};printf("%d %d\\n",p.x,p.y);return 0;}""")
emit("struct_ptr", """
struct P{int x;int y;};
int main(void){struct P p={3,4};struct P*q=&p;q->x=10;printf("%d %d\\n",p.x,q->y);return 0;}""")
emit("struct_pass_val", """
struct P{int x;int y;};
int sum(struct P p){return p.x+p.y;}
int main(void){struct P p={5,6};printf("%d\\n",sum(p));return 0;}""")
emit("struct_pass_ptr", """
struct P{int x;int y;};
void inc(struct P*p){p->x++;p->y++;}
int main(void){struct P p={5,6};inc(&p);printf("%d %d\\n",p.x,p.y);return 0;}""")
emit("struct_return", """
struct P{int x;int y;};
struct P mk(int a,int b){struct P p={a,b};return p;}
int main(void){struct P p=mk(7,8);printf("%d %d\\n",p.x,p.y);return 0;}""")
emit("struct_nested", """
struct Inner{int a;int b;};
struct Outer{struct Inner in;int c;};
int main(void){struct Outer o={{1,2},3};printf("%d %d %d\\n",o.in.a,o.in.b,o.c);return 0;}""")
emit("struct_array", """
struct P{int x;int y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};int s=0;for(int i=0;i<3;i++)s+=a[i].x+a[i].y;printf("%d\\n",s);return 0;}""")
emit("struct_arr_ptr", """
struct P{int x;int y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a;p++;printf("%d %d\\n",p->x,p->y);return 0;}""")
emit("struct_self_ref", """
struct N{int v;int next;};
int main(void){struct N a[3];a[0].v=10;a[0].next=1;a[1].v=20;a[1].next=2;a[2].v=30;a[2].next=-1;int i=0,s=0;while(i>=0){s+=a[i].v;i=a[i].next;}printf("%d\\n",s);return 0;}""")
emit("struct_typedef", """
typedef struct{int x;int y;}Pt;
int main(void){Pt p={3,4};printf("%d\\n",p.x*p.y);return 0;}""")
emit("union_basic", """
union U{int i;char c;};
int main(void){union U u;u.i=65;printf("%d\\n",u.i);u.c='A';printf("%d\\n",u.c);return 0;}""")
emit("union_nested", """
struct In{int a;int b;};
union U{struct In s;int raw;};
int main(void){union U u;u.s.a=100;u.s.b=200;printf("%d %d %d\\n",u.s.a,u.s.b,u.raw);return 0;}""")
emit("struct_field_mut", """
struct P{int x;};
int main(void){struct P p={0};for(int i=0;i<5;i++)p.x+=i;printf("%d\\n",p.x);return 0;}""")

# ---------- PASSING / SCOPE ----------
emit("pass_by_value", """
void f(int x){x=99;}
int main(void){int a=1;f(a);printf("%d\\n",a);return 0;}""")
emit("pass_recursion", """
int fact(int n){return n<=1?1:n*fact(n-1);}
int main(void){printf("%d\\n",fact(5));return 0;}""")
emit("pass_mutual", """
int iseven(int n);int isodd(int n){return n==0?0:iseven(n-1);}
int iseven(int n){return n==0?1:isodd(n-1);}
int main(void){printf("%d %d\\n",iseven(10),isodd(7));return 0;}""")
emit("pass_many_args", """
int f(int a,int b,int c,int d,int e){return a+b*2+c*3+d*4+e*5;}
int main(void){printf("%d\\n",f(1,2,3,4,5));return 0;}""")
emit("scope_shadow", """
int main(void){int x=1;{int x=2;{int x=3;printf("%d",x);}printf("%d",x);}printf("%d\\n",x);return 0;}""")
emit("static_local", """
int counter(void){static int c=0;return ++c;}
int main(void){printf("%d %d %d\\n",counter(),counter(),counter());return 0;}""")
emit("global_var", """
int g=10;
void inc(void){g+=5;}
int main(void){inc();inc();printf("%d\\n",g);return 0;}""")

# ---------- ARITHMETIC / TYPES ----------
emit("arith_ops", """
int main(void){int a=17,b=5;printf("%d %d %d %d %d\\n",a+b,a-b,a*b,a/b,a%b);return 0;}""")
emit("arith_neg", """
int main(void){int a=-7,b=3;printf("%d %d %d\\n",a/b,a%b,-a);return 0;}""")
emit("uint_wrap", """
int main(void){unsigned a=0;a-=1;printf("%u\\n",a);return 0;}""")
emit("uint_cmp_highbit", """
unsigned id(unsigned x){return x;}
int main(void){unsigned a=id(0u)-1u,b=id(1u);printf("%d %d %d\\n",a>b,a<b,b<a);return 0;}""")
emit("char_wrap", """
int main(void){unsigned char c=250;c+=10;printf("%d\\n",c);signed char s=120;s+=20;printf("%d\\n",s);return 0;}""")
emit("bitwise", """
int main(void){int a=0xF0,b=0x0F;printf("%d %d %d %d\\n",a&b,a|b,a^b,~a);return 0;}""")
emit("shifts", """
int main(void){int a=1;printf("%d %d %d\\n",a<<4,256>>2,(-8)>>1);return 0;}""")
emit("compound_assign", """
int main(void){int a=10;a+=5;a-=2;a*=3;a/=4;a%=5;a<<=2;a|=1;printf("%d\\n",a);return 0;}""")
emit("ternary_chain", """
int main(void){for(int i=0;i<5;i++){int r=i==0?100:i==1?200:i==2?300:999;printf("%d ",r);}printf("\\n");return 0;}""")
emit("int_overflow", """
int main(void){int a=2000000000;a+=2000000000;printf("%d\\n",a);return 0;}""")
emit("cast_trunc", """
int main(void){int x=300;char c=(char)x;printf("%d\\n",c);unsigned char u=(unsigned char)x;printf("%d\\n",u);return 0;}""")

# ---------- CONTROL ----------
emit("switch_basic", """
int main(void){for(int i=0;i<4;i++){switch(i){case 0:printf("z");break;case 1:printf("o");break;case 2:printf("t");break;default:printf("?");}}printf("\\n");return 0;}""")
emit("switch_fall", """
int main(void){int x=2,r=0;switch(x){case 1:r+=1;case 2:r+=2;case 3:r+=3;break;case 4:r+=4;}printf("%d\\n",r);return 0;}""")
emit("loop_nested_break", """
int main(void){int c=0;for(int i=0;i<5;i++){for(int j=0;j<5;j++){if(j==3)break;c++;}}printf("%d\\n",c);return 0;}""")
emit("loop_continue", """
int main(void){int s=0;for(int i=0;i<10;i++){if(i%2==0)continue;s+=i;}printf("%d\\n",s);return 0;}""")
emit("while_do", """
int main(void){int i=0,s=0;while(i<5){s+=i;i++;}int j=0;do{s+=j;j++;}while(j<3);printf("%d\\n",s);return 0;}""")
emit("logic_short", """
int sidef(int*c){(*c)++;return 1;}
int main(void){int calls=0;int r=(0&&sidef(&calls))||(1||sidef(&calls));printf("%d %d\\n",r,calls);return 0;}""")

# ---------- STRINGS ----------
emit("str_literal", """
int main(void){printf("%s\\n","hello world");return 0;}""", H_STD)
emit("str_charptr", """
int main(void){const char*s="abc";printf("%s\\n",s);return 0;}""", H_STD)
emit("str_reassign", """
int main(void){const char*s;int k=1;if(k)s="yes";else s="no";printf("%s\\n",s);return 0;}""", H_STD)
emit("str_return", """
const char*pick(int k){return k?"on":"off";}
int main(void){printf("%s %s\\n",pick(1),pick(0));return 0;}""", H_STD)
emit("str_strlen", """
int main(void){printf("%zu\\n",strlen("hello"));return 0;}""", H_STD)
emit("str_strcmp", """
int main(void){printf("%d %d\\n",strcmp("abc","abc")==0,strcmp("abc","abd")<0);return 0;}""", H_STD)
emit("str_array_idx", """
int main(void){char s[]="hello";printf("%c%c\\n",s[0],s[4]);return 0;}""", H_STD)

# ---------- MALLOC ----------
emit("malloc_basic", """
int main(void){int*p=malloc(sizeof(int)*3);p[0]=1;p[1]=2;p[2]=3;printf("%d\\n",p[0]+p[1]+p[2]);free(p);return 0;}""", H_STD)
emit("malloc_loop", """
int main(void){int s=0;for(int i=0;i<5;i++){int*p=malloc(sizeof(int));*p=i*i;s+=*p;free(p);}printf("%d\\n",s);return 0;}""", H_STD)
emit("malloc_struct", """
struct P{int x;int y;};
int main(void){struct P*p=malloc(sizeof(struct P));p->x=3;p->y=4;printf("%d\\n",p->x*p->y);free(p);return 0;}""", H_STD)
emit("malloc_in_fn", """
void setv(int*out){int*p=malloc(sizeof(int));p[0]=99;*out=p[0];free(p);}
int main(void){int r=0;setv(&r);printf("%d\\n",r);return 0;}""", H_STD)

# ---------- ENUM / TYPEDEF / GENERIC ----------
emit("enum_basic", """
enum Color{RED,GREEN=5,BLUE};
int main(void){printf("%d %d %d\\n",RED,GREEN,BLUE);return 0;}""")
emit("generic_type", """
#define tn(x) _Generic((x),int:"int",char:"char",unsigned:"uint",default:"?")
int main(void){int a=1;char c='x';unsigned u=2;printf("%s %s %s\\n",tn(a),tn(c),tn(u));return 0;}""")
emit("sizeof_types", """
int main(void){printf("%zu %zu %zu\\n",sizeof(int),sizeof(char),sizeof(int*));return 0;}""")
emit("fnptr_array", """
int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int main(void){int(*ops[2])(int,int)={add,sub};for(int i=0;i<2;i++)printf("%d ",ops[i](10,3));printf("\\n");return 0;}""")

print(f"generated {n} files")
