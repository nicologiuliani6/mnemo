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
    printf("pid=%d v=%d\n", p->pid, p->v);
}

int main(void) {
    K.procs[0].pid = 10;
    K.procs[0].v = 100;
    K.procs[1].pid = 20;
    K.procs[1].v = 200;
    int i;
    for (i = 0; i < 2; i++) {
        proc_t* p = &K.procs[i];
        use(p);
    }
    return 0;
}
