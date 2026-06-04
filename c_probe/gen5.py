#!/usr/bin/env python3
"""Batch 5: parsing, stringhe, ricorsione, bit-manip, edge-case (con --native-arith dove serve)."""
import os
OUT=os.path.join(os.path.dirname(__file__),"t");os.makedirs(OUT,exist_ok=True)
n=0
H="#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n"
def e(name,body,h=H):
    global n;n+=1;open(os.path.join(OUT,f"{name}.c"),"w").write(h+body+"\n")

# parsing / stringhe
e("ps_atoi_manual","""
int ai(const char*s){int r=0,sg=1;if(*s=='-'){sg=-1;s++;}while(*s>='0'&&*s<='9'){r=r*10+(*s-'0');s++;}return r*sg;}
int main(void){printf("%d %d %d\\n",ai("12345"),ai("-678"),ai("0"));return 0;}""")
e("ps_itoa_manual","""
void it(int x,char*b){int i=0,neg=0;if(x<0){neg=1;x=-x;}char t[16];int j=0;if(x==0)t[j++]='0';while(x){t[j++]='0'+x%10;x/=10;}if(neg)b[i++]='-';while(j)b[i++]=t[--j];b[i]=0;}
int main(void){char b[16];it(-4231,b);printf("%s\\n",b);it(0,b);printf("%s\\n",b);return 0;}""")
e("ps_palindrome","""
int pal(const char*s){int n=0;while(s[n])n++;for(int i=0,j=n-1;i<j;i++,j--)if(s[i]!=s[j])return 0;return 1;}
int main(void){printf("%d %d %d\\n",pal("racecar"),pal("hello"),pal("abba"));return 0;}""")
e("ps_count_vowels","""
int main(void){const char*s="the quick brown fox";int v=0;for(int i=0;s[i];i++){char c=s[i];if(c=='a'||c=='e'||c=='i'||c=='o'||c=='u')v++;}printf("%d\\n",v);return 0;}""")
e("ps_run_length","""
int main(void){const char*s="aaabbbcccd";char out[32];int o=0,i=0;while(s[i]){char c=s[i];int cnt=0;while(s[i]==c){cnt++;i++;}out[o++]=c;out[o++]='0'+cnt;}out[o]=0;printf("%s\\n",out);return 0;}""")
e("ps_caesar","""
int main(void){char s[]="HELLO";int sh=3;for(int i=0;s[i];i++)if(s[i]>='A'&&s[i]<='Z')s[i]='A'+(s[i]-'A'+sh)%26;printf("%s\\n",s);return 0;}""")

# ricorsione
e("rc_hanoi","""
int moves=0;
void h(int n,int f,int t,int v){if(n==0)return;h(n-1,f,v,t);moves++;h(n-1,v,t,f);}
int main(void){h(4,0,2,1);printf("%d\\n",moves);return 0;}""")
e("rc_perm_count","""
int fact(int n){return n<=1?1:n*fact(n-1);}
int main(void){printf("%d %d\\n",fact(6),fact(0));return 0;}""")
e("rc_tree_sum","""
int a[15]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15};
int ts(int i){if(i>=15)return 0;return a[i]+ts(2*i+1)+ts(2*i+2);}
int main(void){printf("%d\\n",ts(0));return 0;}""")
e("rc_mutual2","""
int f(int);int g(int n){return n==0?1:n-f(g(n-1));}
int f(int n){return n==0?0:n-g(f(n-1));}
int main(void){printf("%d %d\\n",f(10),g(10));return 0;}""")

# bit manip
e("bm_count_bits_loop","""
int main(void){int s=0;for(unsigned x=0;x<256;x++){unsigned t=x,c=0;while(t){c+=t&1;t>>=1;}s+=c;}printf("%d\\n",s);return 0;}""")
e("bm_swap_xor","""
int main(void){int a=5,b=9;a^=b;b^=a;a^=b;printf("%d %d\\n",a,b);return 0;}""")
e("bm_set_clear","""
int main(void){unsigned f=0;f|=(1<<3);f|=(1<<7);f&=~(1<<3);printf("%u %d\\n",f,(f>>7)&1);return 0;}""")
e("bm_parity","""
int par(unsigned x){x^=x>>16;x^=x>>8;x^=x>>4;x^=x>>2;x^=x>>1;return x&1;}
int main(void){printf("%d %d %d\\n",par(0x7),par(0xF),par(0x1234));return 0;}""")
e("bm_reverse_byte","""
unsigned char rb(unsigned char b){b=(b&0xF0)>>4|(b&0x0F)<<4;b=(b&0xCC)>>2|(b&0x33)<<2;b=(b&0xAA)>>1|(b&0x55)<<1;return b;}
int main(void){printf("%d %d\\n",rb(1),rb(0x80));return 0;}""")
e("bm_next_pow2","""
unsigned np2(unsigned x){x--;x|=x>>1;x|=x>>2;x|=x>>4;x|=x>>8;x|=x>>16;return x+1;}
int main(void){printf("%u %u %u\\n",np2(5),np2(17),np2(1000));return 0;}""")

# array algos
e("aa_max_subarray","""
int main(void){int a[8]={-2,1,-3,4,-1,2,1,-5};int best=a[0],cur=a[0];for(int i=1;i<8;i++){cur=a[i]>cur+a[i]?a[i]:cur+a[i];if(cur>best)best=cur;}printf("%d\\n",best);return 0;}""")
e("aa_rotate","""
int main(void){int a[6]={1,2,3,4,5,6};int k=2;int tmp[6];for(int i=0;i<6;i++)tmp[(i+k)%6]=a[i];for(int i=0;i<6;i++)printf("%d",tmp[i]);printf("\\n");return 0;}""")
e("aa_dedup_sorted","""
int main(void){int a[10]={1,1,2,3,3,3,4,5,5,6};int w=0;for(int i=0;i<10;i++)if(i==0||a[i]!=a[i-1])a[w++]=a[i];for(int i=0;i<w;i++)printf("%d",a[i]);printf("\\n");return 0;}""")
e("aa_two_sum","""
int main(void){int a[6]={2,7,11,15,3,6},tgt=9;int r=-1;for(int i=0;i<6&&r<0;i++)for(int j=i+1;j<6;j++)if(a[i]+a[j]==tgt){r=i*10+j;break;}printf("%d\\n",r);return 0;}""")
e("aa_histogram","""
int main(void){int data[10]={3,1,4,1,5,9,2,6,5,3};int h[10]={0};for(int i=0;i<10;i++)h[data[i]]++;int mx=0,mxv=0;for(int i=0;i<10;i++)if(h[i]>mx){mx=h[i];mxv=i;}printf("%d %d\\n",mxv,mx);return 0;}""")

# misc realistic
e("mr_temp_convert","""
int main(void){for(int c=0;c<=100;c+=25){int f=c*9/5+32;printf("%d->%d ",c,f);}printf("\\n");return 0;}""")
e("mr_grade","""
char grade(int s){if(s>=90)return 'A';if(s>=80)return 'B';if(s>=70)return 'C';if(s>=60)return 'D';return 'F';}
int main(void){int sc[5]={95,82,71,55,68};for(int i=0;i<5;i++)printf("%c",grade(sc[i]));printf("\\n");return 0;}""")
e("mr_running_stats","""
int main(void){int a[7]={4,8,15,16,23,42,8};int sum=0,mn=a[0],mx=a[0];for(int i=0;i<7;i++){sum+=a[i];if(a[i]<mn)mn=a[i];if(a[i]>mx)mx=a[i];}printf("%d %d %d %d\\n",sum,sum/7,mn,mx);return 0;}""")
e("mr_dice_sim","""
int main(void){unsigned seed=12345;int counts[6]={0};for(int i=0;i<60;i++){seed=seed*1103515245u+12345u;int r=(seed>>16)%6;counts[r]++;}int t=0;for(int i=0;i<6;i++)t+=counts[i];printf("%d\\n",t);return 0;}""")
e("mr_matrix_spiral","""
int main(void){int m[3][3]={{1,2,3},{4,5,6},{7,8,9}};int sum=0;for(int i=0;i<3;i++)sum+=m[0][i]+m[2][i]+m[i][0]+m[i][2];sum-=m[0][0]+m[0][2]+m[2][0]+m[2][2];printf("%d\\n",sum);return 0;}""")

print(f"generated {n} files")
