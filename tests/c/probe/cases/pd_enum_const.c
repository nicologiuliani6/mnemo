#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum{KB=1024,MB=KB*1024};
int main(void){const int x=KB*4;const int y=MB/512;printf("%d %d %d\n",KB,MB,x+y);return 0;}
