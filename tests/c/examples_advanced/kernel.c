#include <stdio.h>
#include <string.h>
#include "mps.h"
#define MNEMO_SYNC_PRINT_DEFINE_MUTEX
#include "mnemo_sync_print.h"

#define MAX_PROCS 4
#define MAX_MEM   256

typedef enum { READY, RUNNING, BLOCKED, DEAD } state_t;

typedef struct {
    int pid;
    state_t state;
    int pc;
    char mem[64];
} process_t;

typedef struct {
    process_t procs[MAX_PROCS];
    mps_t channel; // unico canale kernel <-> kloop
} kernel_t;

kernel_t K;

void sys_write(int pid, const char* msg) {
    printf("[proc %d] %s\n", pid, msg);
}

void proc0(mps_t *mps) { sys_write(0, "hello from proc0"); int t = 0; ssend(mps, t); }
void proc1(mps_t *mps) { sys_write(1, "proc1 running");   int t = 1; ssend(mps, t); }
void proc2(mps_t *mps) { sys_write(2, "proc2 working");   int t = 2; ssend(mps, t); }
void proc3(mps_t *mps) { sys_write(3, "proc3 finishing"); int t = 3; ssend(mps, t); }

/* thread 1: esegue tutti i tick, manda token al kernel dopo ogni processo */
void kloop(mps_t *mps, int *unused) {
    for (int tick = 0; tick < 10; tick++) {
        int idx = tick % MAX_PROCS;
        switch (idx) {
            case 0: proc0(mps); break;
            case 1: proc1(mps); break;
            case 2: proc2(mps); break;
            case 3: proc3(mps); break;
        }
    }
}

/* thread 2: riceve 10 token dal kloop */
void kernel_recv(mps_t *mps, int *answer) {
    for (int tick = 0; tick < 10; tick++) {
        srecv(mps, answer);
        printf("[kernel] processo %d completato tick\n", *answer);
    }
}

void kinit() {
    for (int i = 0; i < MAX_PROCS; i++) {
        K.procs[i].pid = i;
        K.procs[i].state = READY;
        K.procs[i].pc = 0;
        strcpy(K.procs[i].mem, "init");
    }
    init_mutexes(&K.channel);
}

int main() {
    mnemo_sync_print_setup();
    kinit();
    int answer = 0;
    mnemo_pthread_parallel2(kloop, kernel_recv, &K.channel, &K.channel, &answer);
    destroy_mutexes(&K.channel);
    mnemo_sync_print_teardown();
    return 0;
}