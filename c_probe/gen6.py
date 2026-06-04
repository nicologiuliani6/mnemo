#!/usr/bin/env python3
"""Batch 6: linked structures, function tables, parsing, espressioni complesse."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# pointer/struct heavy
e("p6_linked_reverse","""
struct N{int v;int nx;};
int main(void){struct N p[5];for(int i=0;i<5;i++){p[i].v=i+1;p[i].nx=i+1;}p[4].nx=-1;
int head=0,prev=-1;while(head!=-1){int nx=p[head].nx;p[head].nx=prev;prev=head;head=nx;}
int s=0,c=prev;while(c!=-1){s=s*10+p[c].v;c=p[c].nx;}printf("%d\\n",s);return 0;}""")
e("p6_bst_insert","""
struct Node{int v,l,r;};
struct Node tree[20];int nn=0;
int ins(int root,int v){if(root==-1){tree[nn].v=v;tree[nn].l=-1;tree[nn].r=-1;return nn++;}if(v<tree[root].v)tree[root].l=ins(tree[root].l,v);else tree[root].r=ins(tree[root].r,v);return root;}
int cnt(int r){if(r==-1)return 0;return 1+cnt(tree[r].l)+cnt(tree[r].r);}
int main(void){int root=-1;int vals[7]={5,3,8,1,4,7,9};for(int i=0;i<7;i++)root=ins(root,vals[i]);printf("%d\\n",cnt(root));return 0;}""")
e("p6_func_table","""
int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}int mul(int a,int b){return a*b;}int dv(int a,int b){return a/b;}
int main(void){int(*ops[4])(int,int)={add,sub,mul,dv};int r=100;for(int i=0;i<4;i++)r=ops[i](r,2);printf("%d\\n",r);return 0;}""")
e("p6_dispatch_param","""
int sq(int x){return x*x;}int cube(int x){return x*x*x;}
int apply_n(int(*f)(int),int x,int n){for(int i=0;i<n;i++)x=f(x);return x;}
int main(void){printf("%d %d\\n",apply_n(sq,2,3),apply_n(cube,2,2));return 0;}""")
e("p6_struct_ptr_swap_arr","""
struct P{int x,y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a,*q=a+2;struct P t=*p;*p=*q;*q=t;printf("%d %d %d %d\\n",a[0].x,a[0].y,a[2].x,a[2].y);return 0;}""")

# parsing
e("p6_expr_eval","""
int main(void){const char*s="3+4*2-1";int vals[8],vn=0,ops[8],on=0,i=0;
while(s[i]){int num=0;while(s[i]>='0'&&s[i]<='9'){num=num*10+(s[i]-'0');i++;}vals[vn++]=num;if(s[i])ops[on++]=s[i++];}
int res=vals[0];for(int k=0;k<on;k++){if(ops[k]=='+')res+=vals[k+1];else if(ops[k]=='-')res-=vals[k+1];else if(ops[k]=='*')res*=vals[k+1];}printf("%d\\n",res);return 0;}""")
e("p6_csv_sum","""
int main(void){const char*s="10,20,30,40,50";int sum=0,cur=0;for(int i=0;;i++){if(s[i]==','||s[i]==0){sum+=cur;cur=0;if(s[i]==0)break;}else cur=cur*10+(s[i]-'0');}printf("%d\\n",sum);return 0;}""")
e("p6_tokenizer","""
int main(void){const char*s="  hello   world  foo ";int words=0,i=0;while(s[i]){while(s[i]==' ')i++;if(s[i]){words++;while(s[i]&&s[i]!=' ')i++;}}printf("%d\\n",words);return 0;}""")
e("p6_json_depth","""
int main(void){const char*s="{[{}],[[]]}";int d=0,mx=0;for(int i=0;s[i];i++){if(s[i]=='{'||s[i]=='[')d++;else if(s[i]=='}'||s[i]==']')d--;if(d>mx)mx=d;}printf("%d\\n",mx);return 0;}""")

# espressioni complesse
e("p6_precedence","""
int main(void){int a=2,b=3,c=4,d=5;printf("%d %d %d\\n",a+b*c-d,a*b+c*d,(a+b)*(c-d));return 0;}""")
e("p6_chained_ternary","""
int sgn(int x){return x>0?1:x<0?-1:0;}
int main(void){for(int i=-2;i<=2;i++)printf("%d ",sgn(i));printf("\\n");return 0;}""")
e("p6_comma_op","""
int main(void){int a,b,c;a=(b=3,c=4,b+c);printf("%d %d %d\\n",a,b,c);return 0;}""")
e("p6_compound_chain","""
int main(void){int x=64;x>>=2;x|=3;x^=0xF;x&=0x3F;x+=10;x*=2;printf("%d\\n",x);return 0;}""")
e("p6_short_circuit_side","""
int calls=0;int inc(void){calls++;return 1;}
int main(void){int r1=0||inc();int r2=1&&inc();int r3=0&&inc();int r4=1||inc();printf("%d %d %d %d %d\\n",r1,r2,r3,r4,calls);return 0;}""")

# malloc/memory
e("p6_dyn_grow","""
int main(void){int cap=2,len=0;int*a=malloc(sizeof(int)*cap);for(int i=0;i<10;i++){if(len==cap){cap*=2;int*na=malloc(sizeof(int)*cap);for(int k=0;k<len;k++)na[k]=a[k];free(a);a=na;}a[len++]=i*i;}int s=0;for(int i=0;i<len;i++)s+=a[i];printf("%d\\n",s);free(a);return 0;}""")
e("p6_2d_malloc_struct","""
struct Cell{int v;};
int main(void){int R=3,C=3;struct Cell*g=malloc(sizeof(struct Cell)*R*C);for(int i=0;i<R*C;i++)g[i].v=i;int tr=0;for(int i=0;i<R;i++)tr+=g[i*C+i].v;printf("%d\\n",tr);free(g);return 0;}""")
e("p6_string_dup","""
int main(void){char src[]="copyme";int n=0;while(src[n])n++;char*dst=malloc(n+1);for(int i=0;i<=n;i++)dst[i]=src[i];printf("%s\\n",dst);free(dst);return 0;}""")

# char/byte
e("p6_byte_pack","""
int main(void){unsigned char b[4]={0xDE,0xAD,0xBE,0xEF};uint32_t v=0;for(int i=0;i<4;i++)v=(v<<8)|b[i];printf("%08X\\n",v);return 0;}""")
e("p6_endian_swap","""
uint32_t bswap(uint32_t x){return ((x&0xFF)<<24)|((x&0xFF00)<<8)|((x>>8)&0xFF00)|((x>>24)&0xFF);}
int main(void){printf("%08X\\n",bswap(0x12345678u));return 0;}""")
e("p6_nibble_count","""
int main(void){uint32_t x=0x1234ABCD;int counts[16]={0};for(int i=0;i<8;i++){counts[(x>>(i*4))&0xF]++;}int nz=0;for(int i=0;i<16;i++)if(counts[i])nz++;printf("%d\\n",nz);return 0;}""")

print(f"generated {n} files")
