#!/usr/bin/env python3
"""Batch 3: trickier edge cases across all categories."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# pointers tricky
e("pp_ptr_to_ptr_loop","""
int main(void){int x=5;int*p=&x;int**q=&p;int***r=&q;***r=42;printf("%d\\n",x);return 0;}""")
e("pp_arr_ptr_mix","""
int main(void){int a[4]={1,2,3,4};int*p=a;int*q=a+3;int s=0;while(p<=q){s+=*p;p++;}printf("%d\\n",s);return 0;}""")
e("pp_char_count","""
int countc(const char*s,char c){int n=0;while(*s)if(*s++==c)n++;return n;}
int main(void){printf("%d\\n",countc("mississippi",'s'));return 0;}""")
e("pp_strrev","""
void rev(char*s){int n=0;while(s[n])n++;for(int i=0,j=n-1;i<j;i++,j--){char t=s[i];s[i]=s[j];s[j]=t;}}
int main(void){char s[]="hello";rev(s);printf("%s\\n",s);return 0;}""")
e("pp_ptr_struct_field_arr","""
struct P{int a[3];};
int main(void){struct P p={{1,2,3}};struct P*q=&p;q->a[1]=99;printf("%d %d %d\\n",p.a[0],p.a[1],p.a[2]);return 0;}""")
e("pp_2d_via_ptr","""
int main(void){int m[3][3];int*base=&m[0][0];for(int i=0;i<9;i++)base[i]=i*i;printf("%d %d\\n",m[1][1],m[2][2]);return 0;}""")
e("pp_func_ptr_param","""
int apply(int(*f)(int),int x){return f(x);}
int sq(int x){return x*x;}
int main(void){printf("%d\\n",apply(sq,7));return 0;}""")
e("pp_swap_via_pp","""
void sw(int**a,int**b){int*t=*a;*a=*b;*b=t;}
int main(void){int x=1,y=2;int*p=&x,*q=&y;sw(&p,&q);printf("%d %d\\n",*p,*q);return 0;}""")

# structs tricky
e("st_arr_struct_init_loop","""
struct P{int x;int y;};
int main(void){struct P a[4];for(int i=0;i<4;i++){a[i].x=i;a[i].y=i*i;}int s=0;for(int i=0;i<4;i++)s+=a[i].x*a[i].y;printf("%d\\n",s);return 0;}""")
e("st_nested_arr","""
struct Row{int cells[3];};
struct Grid{struct Row rows[2];};
int main(void){struct Grid g;for(int i=0;i<2;i++)for(int j=0;j<3;j++)g.rows[i].cells[j]=i*3+j;int s=0;for(int i=0;i<2;i++)for(int j=0;j<3;j++)s+=g.rows[i].cells[j];printf("%d\\n",s);return 0;}""")
e("st_ptr_arith_struct","""
struct P{int x;int y;};
int main(void){struct P a[4]={{1,1},{2,2},{3,3},{4,4}};struct P*p=a;int s=0;for(int i=0;i<4;i++){s+=(p+i)->x;}printf("%d\\n",s);return 0;}""")
e("st_return_struct_chain","""
struct P{int x;int y;};
struct P add(struct P a,struct P b){struct P r={a.x+b.x,a.y+b.y};return r;}
int main(void){struct P a={1,2},b={3,4},c={5,6};struct P r=add(add(a,b),c);printf("%d %d\\n",r.x,r.y);return 0;}""")
e("st_modify_through_arr_ptr","""
struct P{int v;};
void incall(struct P*a,int n){for(int i=0;i<n;i++)a[i].v++;}
int main(void){struct P a[3]={{10},{20},{30}};incall(a,3);printf("%d %d %d\\n",a[0].v,a[1].v,a[2].v);return 0;}""")
e("st_union_tag","""
struct Var{int tag;union{int i;int b;}u;};
int main(void){struct Var v;v.tag=1;v.u.i=42;printf("%d %d\\n",v.tag,v.u.i);return 0;}""")
e("st_compare","""
struct P{int x;int y;};
int eq(struct P a,struct P b){return a.x==b.x&&a.y==b.y;}
int main(void){struct P a={1,2},b={1,2},c={3,4};printf("%d %d\\n",eq(a,b),eq(a,c));return 0;}""")

# memory tricky
e("mm_malloc_grow","""
int main(void){int n=20;int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i;int s=0;for(int i=0;i<n;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")
e("mm_2d_malloc_flat","""
int main(void){int r=3,c=4;int*m=malloc(sizeof(int)*r*c);for(int i=0;i<r;i++)for(int j=0;j<c;j++)m[i*c+j]=i*c+j;int s=0;for(int i=0;i<r*c;i++)s+=m[i];printf("%d\\n",s);free(m);return 0;}""")
e("mm_malloc_reuse","""
int main(void){int s=0;for(int k=0;k<3;k++){int*a=malloc(sizeof(int)*4);for(int i=0;i<4;i++)a[i]=k*10+i;for(int i=0;i<4;i++)s+=a[i];free(a);}printf("%d\\n",s);return 0;}""")
e("mm_struct_ptr_chain","""
struct N{int v;};
int main(void){struct N*a=malloc(sizeof(struct N)*3);for(int i=0;i<3;i++)a[i].v=(i+1)*100;printf("%d\\n",a[0].v+a[1].v+a[2].v);free(a);return 0;}""")

# control / arithmetic tricky
e("ct_nested_switch","""
int main(void){int r=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++){switch(i){case 0:r+=j;break;case 1:r+=j*2;break;default:r+=j*3;}}printf("%d\\n",r);return 0;}""")
e("ct_goto_free_loop","""
int main(void){int n=0;for(int i=2;i<30;i++){int prime=1;for(int j=2;j*j<=i;j++)if(i%j==0){prime=0;break;}if(prime)n++;}printf("%d\\n",n);return 0;}""")
e("ct_bit_count","""
int popcount(unsigned x){int c=0;while(x){c+=x&1;x>>=1;}return c;}
int main(void){printf("%d %d %d\\n",popcount(7),popcount(255),popcount(1024));return 0;}""")
e("ct_collatz","""
int collatz(int n){int s=0;while(n!=1){if(n%2==0)n/=2;else n=3*n+1;s++;}return s;}
int main(void){printf("%d %d\\n",collatz(27),collatz(6));return 0;}""")
e("ct_signed_shift_mix","""
int main(void){int a=-256;printf("%d %d %d\\n",a>>1,a>>4,a>>8);unsigned u=0xFF00;printf("%u\\n",u>>4);return 0;}""")
e("ct_mod_neg","""
int main(void){printf("%d %d %d %d\\n",-7%3,7%-3,-7%-3,7%3);return 0;}""")
e("ct_overflow_unsigned","""
unsigned f(unsigned a,unsigned b){return a*b;}
int main(void){printf("%u\\n",f(100000u,100000u));return 0;}""")
e("ct_char_arith","""
int main(void){char c='A';c+=5;printf("%c %d\\n",c,c);for(char x='a';x<='e';x++)printf("%c",x);printf("\\n");return 0;}""")

# strings tricky
e("ss_strcat_manual","""
int main(void){char buf[20]="abc";int n=0;while(buf[n])n++;char*add="def";int i=0;while(add[i])buf[n++]=add[i++];buf[n]=0;printf("%s\\n",buf);return 0;}""")
e("ss_strcmp_manual","""
int cmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a-*b;}
int main(void){printf("%d %d %d\\n",cmp("abc","abc")==0,cmp("abc","abd")<0,cmp("abd","abc")>0);return 0;}""")
e("ss_upper","""
int main(void){char s[]="Hello World";for(int i=0;s[i];i++)if(s[i]>='a'&&s[i]<='z')s[i]-=32;printf("%s\\n",s);return 0;}""")
e("ss_word_count","""
int main(void){const char*s="the quick brown fox";int words=0,in=0;for(int i=0;s[i];i++){if(s[i]!=' '){if(!in){words++;in=1;}}else in=0;}printf("%d\\n",words);return 0;}""")
e("ss_digit_sum","""
int main(void){const char*s="a1b2c3d4";int sum=0;for(int i=0;s[i];i++)if(s[i]>='0'&&s[i]<='9')sum+=s[i]-'0';printf("%d\\n",sum);return 0;}""")

# enum / typedef / generic / misc
e("mi_typedef_chain","""
typedef int myint;typedef myint*intptr;
int main(void){myint x=5;intptr p=&x;*p=99;printf("%d\\n",x);return 0;}""")
e("mi_enum_arith","""
enum{LOW=1,MID=10,HIGH=100};
int main(void){int v=LOW+MID+HIGH;printf("%d\\n",v);return 0;}""")
e("mi_const_ptr","""
int main(void){int x=5,y=9;int*const p=&x;*p=10;printf("%d\\n",x);const int*q=&y;printf("%d\\n",*q);return 0;}""")
e("mi_sizeof_expr","""
int main(void){int a[10];printf("%zu %zu\\n",sizeof a,sizeof a[0]);return 0;}""")
e("mi_ternary_nest_assign","""
int main(void){for(int i=0;i<6;i++){int g=i<2?0:i<4?1:2;printf("%d",g);}printf("\\n");return 0;}""")
e("mi_multi_return_paths","""
int classify(int x){if(x<0)return -1;if(x==0)return 0;return 1;}
int main(void){printf("%d %d %d\\n",classify(-5),classify(0),classify(7));return 0;}""")
e("mi_static_accumulate","""
int acc(int x){static int total=0;total+=x;return total;}
int main(void){printf("%d %d %d %d\\n",acc(1),acc(2),acc(3),acc(4));return 0;}""")
e("mi_recursive_array","""
int sumarr(int*a,int n){if(n==0)return 0;return a[0]+sumarr(a+1,n-1);}
int main(void){int a[5]={1,2,3,4,5};printf("%d\\n",sumarr(a,5));return 0;}""")

print(f"generated {n} files")
