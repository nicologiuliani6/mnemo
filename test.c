/*
 * Variabili file-scope il cui nome NON inizia con __mn_p1_: stesso actual __mn_mem{i}
 * passato a entrambe le call nel PAR → client_done e msg condivisi tra i thread.
 * __mn_p1_* restano sulla seconda finestra (come prima) per l’epilogo del main.
 *
 * Il compilatore Kairos vieta per default int condivise nel PAR: Mnemo antepone
 * automaticamente // KAIROS_ALLOW_PAR_SHARED_INT al .kairos quando serve.
 */
typedef int pthread_mutex_t;

int pthread_mutex_init(pthread_mutex_t *m, void *attr);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);
void mnemo_pthread_parallel2(void (*a)(int), void (*b)(int), int, int);


typedef struct {
    _Bool client_done;
    _Bool server_done;
    int msg;
} mps_t;  
mps_t mps;

int __mn_p1_answer;
void ssend(int msg) {
    mps.msg = msg;
    mps.client_done = 1;
    while (mps.server_done == 0) {
        continue;
    }
}
void srecv(int n) {
    (void)n; //placeholder per il parametro passato da main
    while (mps.client_done == 0) {
        continue;
    }
    __mn_p1_answer = mps.msg;
    mps.server_done = 1;
}

int main(void) {
    mnemo_pthread_parallel2(ssend, srecv, 10, 0);
    return __mn_p1_answer;
}
