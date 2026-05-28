#include <stdio.h>
#include <string.h>

#define MAX_PROCS 4
#define MAX_MEM   256

typedef enum {
    READY,
    RUNNING,
    BLOCKED,
    DEAD
} state_t;

typedef struct {
    int pid;
    state_t state;
    int pc;            // program counter simulato
    char mem[64];      // memoria processo
} process_t;

typedef struct {
    process_t procs[MAX_PROCS];
    int current;
} kernel_t;

kernel_t K;

/* "syscalls" simulate */
void sys_write(int pid, const char* msg) {
    printf("[proc %d] %s\n", pid, msg);
}

void sys_yield() {
    K.current = (K.current + 1) % MAX_PROCS;
}

/* scheduler round-robin */
void schedule() {
    for (int i = 0; i < MAX_PROCS; i++) {
        int idx = (K.current + i) % MAX_PROCS;

        if (K.procs[idx].state == READY) {
            K.current = idx;
            K.procs[idx].state = RUNNING;
            return;
        }
    }
}

/* init kernel */
void kinit() {
    for (int i = 0; i < MAX_PROCS; i++) {
        K.procs[i].pid = i;
        K.procs[i].state = READY;
        K.procs[i].pc = 0;
        strcpy(K.procs[i].mem, "init");
    }
    K.current = 0;
}

/* processo finto 0 */
void proc0() {
    sys_write(0, "hello from proc0");
    sys_yield();
}

/* processo finto 1 */
void proc1() {
    sys_write(1, "proc1 running");
    sys_yield();
}

/* processo finto 2 */
void proc2() {
    sys_write(2, "proc2 working");
    sys_yield();
}

/* processo finto 3 */
void proc3() {
    sys_write(3, "proc3 finishing");
    sys_yield();
}

/* dispatch manuale (emulatore-friendly) */
void run_process(process_t* p) {
    if (p->pid == 0) proc0();
    if (p->pid == 1) proc1();
    if (p->pid == 2) proc2();
    if (p->pid == 3) proc3();

    p->state = READY;
}

/* kernel loop */
void kloop() {
    for (int tick = 0; tick < 10; tick++) {
        schedule();

        process_t* p = &K.procs[K.current];
        if (p->state == READY) {
            p->state = RUNNING;
        }

        run_process(p);
    }
}

int main() {
    kinit();
    kloop();
    return 0;
}