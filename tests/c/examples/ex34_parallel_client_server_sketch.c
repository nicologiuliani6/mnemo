/*
 * Stesso schema di test.c in root: parallel2, mutex π per-worker, int file-scope.
 * make compile / make test lo includono.
 */
typedef int pthread_mutex_t;

int pthread_mutex_init(pthread_mutex_t *m, void *attr);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);

void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));

int client_done;
int __mn_p1_answer;

void client(void) {
    pthread_mutex_t m;
    pthread_mutex_init(&m, 0);
    pthread_mutex_lock(&m);
    client_done = 1;
    pthread_mutex_unlock(&m);
    pthread_mutex_destroy(&m);
}

void server(void) {
    pthread_mutex_t m;
    pthread_mutex_init(&m, 0);
    pthread_mutex_lock(&m);
    __mn_p1_answer = 42;
    pthread_mutex_unlock(&m);
    pthread_mutex_destroy(&m);
}

int main(void) {
    mnemo_pthread_parallel2(client, server);
    return client_done + __mn_p1_answer;
}
