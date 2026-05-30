#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    printf("start\n");
    if (argc > 100) {
        printf("never\n");
        exit(7);
    }
    printf("end\n");
    return 0;
}
