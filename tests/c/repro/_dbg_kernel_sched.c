#include <stdio.h>

typedef enum { READY, RUNNING, DEAD } state_t;

typedef struct {
    int pid;
    state_t state;
} proc_t;

typedef struct {
    proc_t procs[2];
    int cur;
} ker_t;

ker_t K;

void sched(void) {
    for (int i = 0; i < 2; i++) {
        int idx = (K.cur + i) % 2;
        if (K.procs[idx].state == READY) {
            K.cur = idx;
            K.procs[idx].state = RUNNING;
            return;
        }
    }
}

void worker(proc_t* p) {
    if (p->pid == 0) printf("p0\n");
    if (p->pid == 1) printf("p1\n");
    p->state = READY;
}

int main(void) {
    K.procs[0].pid = 0; K.procs[0].state = READY;
    K.procs[1].pid = 1; K.procs[1].state = READY;
    K.cur = 0;

    int tick;
    for (tick = 0; tick < 3; tick++) {
        sched();
        proc_t* p = &K.procs[K.cur];
        worker(p);
    }
    return 0;
}
