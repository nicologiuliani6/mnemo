#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){for(int n=-3;n<=3;n++){int m=n>>31;printf("%d ",(n^m)-m);}printf("\n");return 0;}
