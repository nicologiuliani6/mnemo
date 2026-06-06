#!/usr/bin/env python3
"""Batch 4: programmi realistici/algoritmici per stanare bug residui."""
import os
OUT=os.path.join(os.path.dirname(__file__),"cases");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# algoritmi
e("alg_quicksort","""
void qs(int*a,int lo,int hi){if(lo>=hi)return;int p=a[hi],i=lo;for(int j=lo;j<hi;j++)if(a[j]<p){int t=a[i];a[i]=a[j];a[j]=t;i++;}int t=a[i];a[i]=a[hi];a[hi]=t;qs(a,lo,i-1);qs(a,i+1,hi);}
int main(void){int a[8]={5,2,8,1,9,3,7,4};qs(a,0,7);for(int i=0;i<8;i++)printf("%d",a[i]);printf("\\n");return 0;}""")
e("alg_binsearch","""
int bs(int*a,int n,int x){int lo=0,hi=n-1;while(lo<=hi){int m=(lo+hi)/2;if(a[m]==x)return m;if(a[m]<x)lo=m+1;else hi=m-1;}return -1;}
int main(void){int a[7]={1,3,5,7,9,11,13};printf("%d %d %d\\n",bs(a,7,7),bs(a,7,1),bs(a,7,8));return 0;}""")
e("alg_fib_iter","""
int main(void){long long a=0,b=1;for(int i=0;i<40;i++){long long c=a+b;a=b;b=c;}printf("%lld\\n",a);return 0;}""")
e("alg_sieve","""
int main(void){int s[50];for(int i=0;i<50;i++)s[i]=1;s[0]=s[1]=0;for(int i=2;i<50;i++)if(s[i])for(int j=2*i;j<50;j+=i)s[j]=0;int c=0;for(int i=0;i<50;i++)c+=s[i];printf("%d\\n",c);return 0;}""")
e("alg_gcd_lcm","""
int gcd(int a,int b){return b?gcd(b,a%b):a;}
int main(void){int a=12,b=18;printf("%d %d\\n",gcd(a,b),a/gcd(a,b)*b);return 0;}""")
e("alg_pow_mod","""
long long pm(long long b,long long e,long long m){long long r=1;b%=m;while(e>0){if(e&1)r=r*b%m;e>>=1;b=b*b%m;}return r;}
int main(void){printf("%lld\\n",pm(7,256,13));return 0;}""")
e("alg_matrix_id","""
int main(void){int m[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)m[i][j]=(i==j);int tr=0;for(int i=0;i<4;i++)tr+=m[i][i];printf("%d\\n",tr);return 0;}""")
e("alg_str_tokenize","""
int main(void){const char*s="a,bb,ccc,d";int parts=1;for(int i=0;s[i];i++)if(s[i]==',')parts++;printf("%d\\n",parts);return 0;}""")

# hash / crypto-lite
e("cr_fnv1a","""
unsigned fnv(const char*s){unsigned h=2166136261u;while(*s){h^=(unsigned char)*s++;h*=16777619u;}return h;}
int main(void){printf("%u\\n",fnv("hello"));return 0;}""")
e("cr_crc_lite","""
uint32_t crc(const char*s){uint32_t c=0xFFFFFFFFu;while(*s){c^=(unsigned char)*s++;for(int i=0;i<8;i++)c=(c>>1)^(0xEDB88320u&(-(c&1)));}return ~c;}
int main(void){printf("%08X\\n",crc("123456789"));return 0;}""")
e("cr_xor_cipher","""
int main(void){char buf[]="SECRET";unsigned char k=0x5A;for(int i=0;buf[i];i++)buf[i]^=k;for(int i=0;buf[i];i++)buf[i]^=k;printf("%s\\n",buf);return 0;}""")
e("cr_rotl","""
uint32_t rotl(uint32_t x,int n){return (x<<n)|(x>>(32-n));}
int main(void){printf("%08X %08X\\n",rotl(0x12345678u,8),rotl(0xABCDEF01u,16));return 0;}""")
e("cr_u64_hex","""
int main(void){uint64_t v=0x0123456789ABCDEFull;for(int i=15;i>=0;i--)printf("%X",(unsigned)((v>>(i*4))&0xF));printf("\\n");return 0;}""")
e("cr_bit_reverse","""
unsigned br(unsigned x){unsigned r=0;for(int i=0;i<32;i++){r=(r<<1)|(x&1);x>>=1;}return r;}
int main(void){printf("%08X\\n",br(0x00000001u));return 0;}""")

# data structures (array-backed)
e("ds_stack","""
int main(void){int st[100],top=0;for(int i=1;i<=10;i++)st[top++]=i*i;int s=0;while(top)s+=st[--top];printf("%d\\n",s);return 0;}""")
e("ds_queue_ring","""
int main(void){int q[8],head=0,tail=0,cnt=0;for(int i=0;i<5;i++){q[tail]=i*10;tail=(tail+1)%8;cnt++;}int s=0;while(cnt){s+=q[head];head=(head+1)%8;cnt--;}printf("%d\\n",s);return 0;}""")
e("ds_linked_pool","""
struct Node{int val;int next;};
int main(void){struct Node pool[10];int free=0;int head=-1;for(int i=0;i<5;i++){int n=free++;pool[n].val=(i+1)*7;pool[n].next=head;head=n;}int s=0,c=head;while(c!=-1){s+=pool[c].val;c=pool[c].next;}printf("%d\\n",s);return 0;}""")
e("ds_hashmap_lite","""
int main(void){int keys[16],vals[16];for(int i=0;i<16;i++)keys[i]=-1;int ks[5]={3,17,8,3,25};for(int i=0;i<5;i++){int h=ks[i]%16;while(keys[h]!=-1&&keys[h]!=ks[i])h=(h+1)%16;keys[h]=ks[i];vals[h]++;}int found=0;for(int i=0;i<16;i++)if(keys[i]!=-1)found++;printf("%d\\n",found);return 0;}""")
e("ds_2d_dynamic","""
int main(void){int R=3,C=4;int*m=malloc(sizeof(int)*R*C);for(int i=0;i<R;i++)for(int j=0;j<C;j++)m[i*C+j]=i*10+j;int mx=0;for(int i=0;i<R*C;i++)if(m[i]>mx)mx=m[i];printf("%d\\n",mx);free(m);return 0;}""")

# struct-heavy
e("sh_vec3","""
struct V{int x,y,z;};
int dot(struct V a,struct V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
struct V add(struct V a,struct V b){struct V r={a.x+b.x,a.y+b.y,a.z+b.z};return r;}
int main(void){struct V a={1,2,3},b={4,5,6};struct V c=add(a,b);printf("%d %d\\n",dot(a,b),dot(c,c));return 0;}""")
e("sh_matrix_struct","""
struct M{int d[2][2];};
struct M mul(struct M a,struct M b){struct M r;for(int i=0;i<2;i++)for(int j=0;j<2;j++){r.d[i][j]=0;for(int k=0;k<2;k++)r.d[i][j]+=a.d[i][k]*b.d[k][j];}return r;}
int main(void){struct M a={{{1,2},{3,4}}},b={{{5,6},{7,8}}};struct M c=mul(a,b);printf("%d %d %d %d\\n",c.d[0][0],c.d[0][1],c.d[1][0],c.d[1][1]);return 0;}""")
e("sh_state_machine","""
struct SM{int state;int count;};
void step(struct SM*m,int in){if(m->state==0&&in)m->state=1;else if(m->state==1&&!in){m->state=0;m->count++;}}
int main(void){struct SM m={0,0};int seq[8]={1,0,1,1,0,1,0,0};for(int i=0;i<8;i++)step(&m,seq[i]);printf("%d\\n",m.count);return 0;}""")

# edge arithmetic
e("ea_mixed_width","""
int main(void){uint8_t a=200;uint16_t b=60000;uint32_t c=4000000000u;printf("%u %u %u\\n",(unsigned)(a+100),(unsigned)(b+10000),c+1000000000u);return 0;}""")
e("ea_signed_unsigned_cmp","""
int main(void){int a=-1;unsigned b=1;printf("%d\\n",(unsigned)a>b);return 0;}""")
e("ea_div_round","""
int main(void){for(int n=-5;n<=5;n++)printf("%d ",(n+10)/3-3);printf("\\n");return 0;}""")
e("ea_abs_manual","""
int main(void){for(int n=-3;n<=3;n++){int m=n>>31;printf("%d ",(n^m)-m);}printf("\\n");return 0;}""")

print(f"generated {n} files")
