#!/usr/bin/env python3
"""Batch 15: ancora corner — ptr diff types, nested ternary assign, switch in
   loop with state, struct ptr arith, recursion fib-memo, bit tricks, casts."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# fibonacci memoized
e("pf_fib_memo","""
int memo[40];
int fib(int n){if(n<2)return n;if(memo[n])return memo[n];return memo[n]=fib(n-1)+fib(n-2);}
int main(void){printf("%d %d %d\\n",fib(10),fib(20),fib(30));return 0;}""")

# struct pointer arithmetic
e("pf_struct_ptr_arith","""
struct P{int x,y;};
int main(void){struct P a[5]={{0,0},{1,1},{2,4},{3,9},{4,16}};struct P*p=a;
int s=0;for(int i=0;i<5;i++){s+=(p+i)->x+(p+i)->y;}p+=4;s+=p->y;printf("%d\\n",s);return 0;}""")

# nested ternary as assignment value
e("pf_ternary_assign","""
int main(void){int s=0;for(int i=-3;i<=3;i++){int v=i<0?-i:i>0?i*2:100;s+=v;}printf("%d\\n",s);return 0;}""")

# switch state machine in loop
e("pf_state_loop","""
int main(void){int st=0,out=0;const char*cmds="++--+";for(int i=0;cmds[i];i++){switch(cmds[i]){case '+':out+=st<2?5:1;st++;break;case '-':out-=1;st--;break;}}printf("%d %d\\n",out,st);return 0;}""")

# casts between int/unsigned/char
e("pf_casts","""
int main(void){int i=300;char c=(char)i;unsigned u=(unsigned)c;int back=(int)(unsigned char)i;
printf("%d %d %d\\n",(int)c,u,back);return 0;}""")

# bit tricks: count set bits, lowest set
e("pf_bit_tricks","""
int popcount(unsigned x){int c=0;while(x){x&=x-1;c++;}return c;}
int main(void){printf("%d %d %d\\n",popcount(0xFF),popcount(0x1234),popcount(0));return 0;}""")

# array reverse + sum interleaved
e("pf_arr_reverse","""
int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i+1;
for(int i=0,j=9;i<j;i++,j--){int t=a[i];a[i]=a[j];a[j]=t;}
int s=0;for(int i=0;i<10;i++)s+=a[i]*(i+1);printf("%d\\n",s);return 0;}""")

# nested function pointer dispatch with state
e("pf_calc","""
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}int mx(int a,int b){return a>b?a:b;}
int main(void){int(*ops[3])(int,int)={add,mul,mx};int acc=2;for(int i=0;i<9;i++)acc=ops[i%3](acc,i);printf("%d\\n",acc);return 0;}""")

# multidim init partial
e("pf_md_partial","""
int main(void){int m[3][3]={{1,2},{4},{7,8,9}};int s=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++)s+=m[i][j];printf("%d\\n",s);return 0;}""")

# string to int and back manual
e("pf_atoi_itoa","""
int my_atoi(const char*s){int v=0,sign=1,i=0;if(s[0]=='-'){sign=-1;i=1;}while(s[i]){v=v*10+(s[i]-'0');i++;}return sign*v;}
int main(void){printf("%d %d\\n",my_atoi("12345"),my_atoi("-678"));return 0;}""")

# pointer to struct member
e("pf_member_ptr","""
struct S{int a,b,c;};
int main(void){struct S s={1,2,3};int*p=&s.b;*p=20;int*q=&s.a;printf("%d %d %d %d\\n",s.a,s.b,s.c,*q);return 0;}""")

# do-while with break
e("pf_dowhile_break","""
int main(void){int i=0,s=0;do{i++;if(i==7)break;if(i%2==0)continue;s+=i;}while(i<100);printf("%d %d\\n",s,i);return 0;}""")

# nested loops triangular
e("pf_triangular","""
int main(void){int s=0;for(int i=1;i<=10;i++)for(int j=1;j<=i;j++)s+=i*j;printf("%d\\n",s);return 0;}""")

# global array mutation across calls
e("pf_global_arr","""
int data[10];
void fill(int start){for(int i=0;i<10;i++)data[i]=start+i;}
int sum(void){int s=0;for(int i=0;i<10;i++)s+=data[i];return s;}
int main(void){fill(100);printf("%d ",sum());fill(0);printf("%d\\n",sum());return 0;}""")

# conditional expression chains
e("pf_cond_chain","""
int grade(int s){return s>=90?4:s>=80?3:s>=70?2:s>=60?1:0;}
int main(void){int t=0;int scores[5]={95,82,71,55,88};for(int i=0;i<5;i++)t=t*10+grade(scores[i]);printf("%d\\n",t);return 0;}""")

# xor swap without temp
e("pf_xor_swap","""
int main(void){int a=17,b=42;a^=b;b^=a;a^=b;printf("%d %d\\n",a,b);return 0;}""")

print(f"generated {n} files")
