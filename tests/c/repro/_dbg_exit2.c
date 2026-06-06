// mnemo-main-argc: 1
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    printf("start argc=%d\n", argc);
    if (argc == 1) {
        exit(42);
    }
    printf("end\n");
    return 0;
}
