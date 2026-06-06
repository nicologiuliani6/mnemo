#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Node{int v,l,r;};
struct Node tree[20];int nn=0;
int ins(int root,int v){if(root==-1){tree[nn].v=v;tree[nn].l=-1;tree[nn].r=-1;return nn++;}if(v<tree[root].v)tree[root].l=ins(tree[root].l,v);else tree[root].r=ins(tree[root].r,v);return root;}
int cnt(int r){if(r==-1)return 0;return 1+cnt(tree[r].l)+cnt(tree[r].r);}
int main(void){int root=-1;int vals[7]={5,3,8,1,4,7,9};for(int i=0;i<7;i++)root=ins(root,vals[i]);printf("%d\n",cnt(root));return 0;}
