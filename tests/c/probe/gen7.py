#!/usr/bin/env python3
"""Batch 7: edge cases — static locals, designated init, neg div/mod, char sign,
   nested struct assign, multidim param, ptr-to-array-of-struct, compound."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# static local var persists across calls
e("p7_static_local","""
int counter(void){static int c=0;c++;return c;}
int main(void){int s=0;for(int i=0;i<5;i++)s+=counter();printf("%d\\n",s);return 0;}""")

# designated initializers
e("p7_desig_init","""
int main(void){int a[8]={[2]=20,[5]=50,[0]=1};int s=0;for(int i=0;i<8;i++)s+=a[i];printf("%d\\n",s);return 0;}""")
e("p7_desig_struct","""
struct P{int x,y,z;};
int main(void){struct P p={.z=9,.x=1};printf("%d %d %d\\n",p.x,p.y,p.z);return 0;}""")

# negative div/mod (C truncation toward zero)
e("p7_neg_divmod","""
int main(void){int pairs[6][2]={{-7,2},{7,-2},{-7,-2},{-1,3},{1,-3},{-8,3}};
for(int i=0;i<6;i++)printf("%d %d\\n",pairs[i][0]/pairs[i][1],pairs[i][0]%pairs[i][1]);return 0;}""")

# char signedness
e("p7_char_sign","""
int main(void){char c=-1;unsigned char u=255;int sc=c;int su=u;printf("%d %d\\n",sc,su);
signed char sc2=200;printf("%d\\n",sc2);return 0;}""")

# nested struct copy via ptr
e("p7_nested_struct_ptr","""
struct In{int a,b;};struct Out{struct In i;int tag;};
void cp(struct Out*d,struct Out*s){*d=*s;}
int main(void){struct Out x={{3,4},7};struct Out y;cp(&y,&x);y.i.a=99;
printf("%d %d %d | %d %d %d\\n",x.i.a,x.i.b,x.tag,y.i.a,y.i.b,y.tag);return 0;}""")

# multidim array param
e("p7_multidim_param","""
int sum2d(int m[3][3]){int s=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++)s+=m[i][j];return s;}
int main(void){int m[3][3]={{1,2,3},{4,5,6},{7,8,9}};printf("%d\\n",sum2d(m));return 0;}""")

# ptr to array of structs, arithmetic
e("p7_ptr_struct_arith","""
struct V{int v;};
int main(void){struct V arr[5];for(int i=0;i<5;i++)arr[i].v=i*i;
struct V*p=arr;int s=0;for(int i=0;i<5;i++)s+=(p+i)->v;
p+=2;s+=p->v;p--;s+=p->v;printf("%d\\n",s);return 0;}""")

# compound assignment on struct field via ptr
e("p7_field_compound","""
struct C{int n;};
int main(void){struct C c={10};struct C*p=&c;p->n+=5;p->n*=2;p->n-=3;printf("%d\\n",c.n);return 0;}""")

# array of pointers to int
e("p7_ptr_array","""
int main(void){int a=1,b=2,c=3;int*pa[3]={&a,&b,&c};int s=0;for(int i=0;i<3;i++)s+=*pa[i];
*pa[1]=20;s+=b;printf("%d\\n",s);return 0;}""")

# do-while with continue/break
e("p7_dowhile_cb","""
int main(void){int i=0,s=0;do{i++;if(i%2==0)continue;if(i>9)break;s+=i;}while(i<20);printf("%d\\n",s);return 0;}""")

# goto-free state machine via switch in loop
e("p7_state_machine","""
int main(void){int st=0,steps=0,x=0;while(st!=3&&steps<100){steps++;switch(st){
case 0:x+=1;st=1;break;case 1:x*=2;st=2;break;case 2:x-=1;if(x>20)st=3;else st=0;break;}}
printf("%d %d\\n",x,steps);return 0;}""")

# unsigned overflow wrap
e("p7_uwrap","""
int main(void){unsigned int x=0xFFFFFFFFu;x+=2;unsigned int y=0;y-=1;
printf("%u %u\\n",x,y);return 0;}""")

# pointer difference / comparison
e("p7_ptrdiff","""
int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i;int*p=&a[2];int*q=&a[7];
printf("%ld %d\\n",(long)(q-p),(int)(p<q));return 0;}""")

# bit fields via masking (manual)
e("p7_bitpack","""
int main(void){unsigned int packed=0;int r=5,g=10,b=15;
packed=(r<<8)|(g<<4)|b;int xr=(packed>>8)&0xF,xg=(packed>>4)&0xF,xb=packed&0xF;
printf("%d %d %d %u\\n",xr,xg,xb,packed);return 0;}""")

print(f"generated {n} files")
