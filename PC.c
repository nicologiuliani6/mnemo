#include "mps.h"

void mnemo_pthread_parallel2(
    void (*a)(mps_t *, int),
    void (*b)(mps_t *, int),
    mps_t *arg_a,
    mps_t *arg_b,
    int *answer_b);


#define N 10
void producer(mps_t *m) {
    for (int i = 0; i < N; i++) {
        ssend(m, i);
    }
}

void consumer(mps_t *m, int *answer) {
    for (int i = 0; i < N; i++) {
        srecv(m, answer);
    }
}

int main(int argc, char *argv[]) {
    mps_t mps;
    int answer = 0;
    init_mutexes();
    mnemo_pthread_parallel2(producer, consumer, &mps, &mps, &answer);
    destroy_mutexes();
    return answer;
}
