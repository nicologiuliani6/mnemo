/*
 * pthread_* in Mnemo: non sono POSIX reali.
 * - mnemo_pthread_parallel2(f, g) → Kairos par/rap (due thread nella VM).
 * - mnemo_pthread_start(f) / mnemo_pthread_start1(f, arg) → un ramo par/rap; vedi ex31.
 * - mnemo_pthread_parallel_with(w,c) / _with1(w,arg,c) → par w() and c() rap (ex32).
 * - pthread_mutex_* su `pthread_mutex_t` → canale Kairos con token (π-calculus).
 *
 * Richiesto: `typedef int pthread_mutex_t;` e prototipi delle API sotto.
 */
typedef int pthread_mutex_t;

int pthread_mutex_init(pthread_mutex_t *m, void *attr);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));

void worker_a(void) {
    pthread_mutex_t m;
    pthread_mutex_init(&m, 0);
    pthread_mutex_lock(&m);
    pthread_mutex_unlock(&m);
    pthread_mutex_destroy(&m);
}

void worker_b(void) {
    pthread_mutex_t m;
    pthread_mutex_init(&m, 0);
    pthread_mutex_lock(&m);
    pthread_mutex_unlock(&m);
    pthread_mutex_destroy(&m);
}

int main(void) {
    mnemo_pthread_parallel2(worker_a, worker_b);
    return 0;
}
