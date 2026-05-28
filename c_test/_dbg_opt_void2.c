#include <stdio.h>

typedef struct {
    int pid;
    int v;
} proc_t;

typedef struct {
    proc_t procs[2];
} ker_t;

ker_t K;

void use(proc_t* p) {
    printf("pid=%d\n", p->pid);
}

int main(void) {
    K.procs[0].pid = 10;
    K.procs[1].pid = 20;
    proc_t* p0 = &K.procs[0];
    proc_t* p1 = &K.procs[1];
    use(p0);
    use(p1);
    return 0;
}
