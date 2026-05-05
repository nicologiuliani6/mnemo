/*
 * Fixture per test layout (partition / campo payload condiviso).
 * Replica la struttura di PC.c + ramo MNEMO di mps.h senza dipendere da c_test/.
 * Non va eseguito: solo parse + compute_program_mem_layout.
 */
typedef int pthread_mutex_t;
int pthread_mutex_init(pthread_mutex_t *m, void *attr);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);

typedef struct {
    int payload;
    int __mn_p1_answer;
    pthread_mutex_t g_cs;
    pthread_mutex_t g_slot_free;
    pthread_mutex_t g_data_ready;
} mps_t;

static inline void init_mutexes(mps_t *m) {
    pthread_mutex_init(&m->g_cs, 0);
    pthread_mutex_init(&m->g_slot_free, 0);
    pthread_mutex_init(&m->g_data_ready, 0);
    pthread_mutex_lock(&m->g_data_ready);
}

static inline void destroy_mutexes(mps_t *m) {
    pthread_mutex_unlock(&m->g_data_ready);
    pthread_mutex_destroy(&m->g_cs);
    pthread_mutex_destroy(&m->g_slot_free);
    pthread_mutex_destroy(&m->g_data_ready);
}

static inline void ssend(mps_t *m, int msg) {
    pthread_mutex_lock(&m->g_slot_free);
    pthread_mutex_lock(&m->g_cs);
    m->payload = msg;
    pthread_mutex_unlock(&m->g_cs);
    pthread_mutex_unlock(&m->g_data_ready);
}

static inline void srecv(mps_t *m, int *answer) {
    pthread_mutex_lock(&m->g_data_ready);
    pthread_mutex_lock(&m->g_cs);
    *answer = m->payload;
    pthread_mutex_unlock(&m->g_cs);
    pthread_mutex_unlock(&m->g_slot_free);
}

void mnemo_pthread_parallel2(
    void (*a)(mps_t *, int),
    void (*b)(mps_t *, int),
    mps_t *arg_a,
    mps_t *arg_b,
    int *answer_b);

#define N 2
void producer(mps_t *mps) {
    for (int i = 0; i < N; i++) {
        ssend(mps, i);
    }
}

void consumer(mps_t *mps, int *answer) {
    for (int i = 0; i < N; i++) {
        srecv(mps, answer);
    }
}

int main(void) {
    mps_t mps;
    int answer = 0;
    init_mutexes(&mps);
    mnemo_pthread_parallel2(producer, consumer, &mps, &mps, &answer);
    destroy_mutexes(&mps);
    return answer;
}
