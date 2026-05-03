/*
 * mps.h — API mp sincrono
 *
 * Tipi ed entrypoint pubblici:
 *   – `mps_t`           stato messaggio condiviso tra i due lati.
 *   – `init_mutexes`    inizializza i mutex globali usati dal protocollo.
 *   – `destroy_mutexes` rilascia quei mutex.
 *   – `ssend`           pubblica un valore intero nel messaggio.
 *   – `srecv`           copia nel puntatore `answer` il valore letto dal messaggio.
 *
 * Oggetti globali esposti:
 *   – `g_cs`            mutex per le sezioni critiche su payload / answer.
 *   – `g_xfer`          mutex di hand-off tra invio e ricezione per round.
 */

 typedef int pthread_mutex_t;

 int pthread_mutex_init(pthread_mutex_t *m, void *attr);
 int pthread_mutex_lock(pthread_mutex_t *m);
 int pthread_mutex_unlock(pthread_mutex_t *m);
 int pthread_mutex_destroy(pthread_mutex_t *m);

 typedef struct {
     int payload;
     int __mn_p1_answer;
 } mps_t;

pthread_mutex_t g_cs;
pthread_mutex_t g_xfer;

/* Inizializza `g_cs` e `g_xfer`; blocca `g_xfer` prima che partano i worker. */
void init_mutexes() {
    pthread_mutex_init(&g_cs, 0);
    pthread_mutex_init(&g_xfer, 0);
    pthread_mutex_lock(&g_xfer);
}

/* Distrugge `g_cs` e `g_xfer`. */
void destroy_mutexes() {
    pthread_mutex_destroy(&g_cs);
    pthread_mutex_destroy(&g_xfer);
}

/* `m` puntatore al messaggio; `msg` valore da memorizzare in `m->payload`. */
 void ssend(mps_t *m, int msg) {
     pthread_mutex_lock(&g_cs);
     m->payload = msg;
     pthread_mutex_unlock(&g_cs);
     pthread_mutex_unlock(&g_xfer);
 }

/* `m` messaggio; `answer` destinazione della lettura (una parola intera). */
 void srecv(mps_t *m, int* answer) {
     pthread_mutex_lock(&g_xfer);
     pthread_mutex_lock(&g_cs);
     *answer = m->payload;
     pthread_mutex_unlock(&g_cs);
     pthread_mutex_unlock(&g_xfer);
 }
