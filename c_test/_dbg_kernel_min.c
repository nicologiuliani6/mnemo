#include <stdio.h>

typedef struct {
    int pid;
    int state;
} proc_t;

typedef struct {
    proc_t procs[2];
    int cur;
} ker_t;

ker_t K;

void worker(proc_t* p) {
    if (p->pid == 0) printf("p0 run\n");
    if (p->pid == 1) printf("p1 run\n");
}

int main(void) {
    K.procs[0].pid = 0;
    K.procs[0].state = 1;
    K.procs[1].pid = 1;
    K.procs[1].state = 1;
    K.cur = 0;

    int tick;
    for (tick = 0; tick < 3; tick++) {
        proc_t* p = &K.procs[K.cur];
        worker(p);
        K.cur = (K.cur + 1) % 2;
    }
    return 0;
}
