#include "mps.h"
#define MNEMO_SYNC_PRINT_DEFINE_MUTEX //mutex su printf
#include "mnemo_sync_print.h"

void mnemo_pthread_parallel2(
    void (*a)(mps_t *, int),
    void (*b)(mps_t *, int),
    mps_t *arg_a,
    mps_t *arg_b,
    int *answer_b);

#define N 10
void producer(mps_t *mps) {
    for (int i = 0; i < N; i++) {
        printf("producer: %d\n", i);
        ssend(mps, i);
    }
}

void consumer(mps_t *mps, int *answer) {
    for (int i = 0; i < N; i++) {
        srecv(mps, answer);
        printf("consumer: %d\n", *answer);
    }
}

int main(void) {
    mps_t mps;
    int answer = 0;
    init_mutexes(&mps);
    mnemo_sync_print_setup();
    mnemo_pthread_parallel2(producer, consumer, &mps, &mps, &answer);
    mnemo_sync_print_teardown();
    destroy_mutexes(&mps);
    return answer;
}
