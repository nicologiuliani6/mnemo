#include <stdio.h>

typedef struct {
    int pid;
    int v;
} proc_t;

typedef struct {
    proc_t procs[2];
} ker_t;

ker_t K;

void use(int pid) {
    printf("pid=%d\n", pid);
}

int main(void) {
    K.procs[0].pid = 10;
    use(K.procs[0].pid);
    return 0;
}
