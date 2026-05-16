/*
 * mps.h — API mp sincrono
 *
 * Compilazione:
 *   VM mnemo  →  -DMNEMO  (o definito automaticamente dal toolchain)
 *   gcc/clang →  gcc PC.c -lpthread
 */

 #ifndef MPS_H
 #define MPS_H
 
 #ifdef MNEMO
 typedef int pthread_mutex_t;
 int pthread_mutex_init(pthread_mutex_t *m, void *attr);
 int pthread_mutex_lock(pthread_mutex_t *m);
 int pthread_mutex_unlock(pthread_mutex_t *m);
 int pthread_mutex_destroy(pthread_mutex_t *m);
 #else
 #include <pthread.h>
 #include <semaphore.h>
 /* I warning di firma incompatibile su mnemo_pthread_parallel2 sono attesi:
    la VM usa una firma generica (mps_t*, int) per entrambi gli argomenti,
    ma producer e consumer hanno firme concrete diverse. */
 #pragma GCC diagnostic ignored "-Wcast-function-type"
 #pragma GCC diagnostic ignored "-Wincompatible-pointer-types"
 #endif
 
 #ifdef MNEMO
 /*
  * Singolo canale `lane` (pthread_mutex_t → channel Kairos) che trasporta msg
  * direttamente nel token: Mnemo lower ssend/srecv come Kairos `ssend(<msg>, lane)`
  * / `srecv(<msg>, lane)`. Eliminato `payload`/`__mn_p1_answer` int condivisi
  * (rompevano l'invertibilità: due thread → stesse __mn_mem cells = race).
  */
 typedef struct {
     /* placeholder int per dare un indirizzo a `&mps` (Mnemo richiede first-field int). */
     int __mn_p1_answer;
     pthread_mutex_t lane;
 } mps_t;

 static inline void init_mutexes(mps_t *m) {
     pthread_mutex_init(&m->lane, 0);
 }

 static inline void destroy_mutexes(mps_t *m) {
     pthread_mutex_destroy(&m->lane);
 }

 static inline void ssend(mps_t *m, int msg) {
     /* Mnemo lower → Kairos `ssend(<msg>, __mn_mtx_..._lane)`. */
     pthread_mutex_unlock(&m->lane);
 }

 static inline void srecv(mps_t *m, int *answer) {
     /* Mnemo lower → Kairos `srecv(<*answer>, __mn_mtx_..._lane)`. */
     pthread_mutex_lock(&m->lane);
 }
 #else
 /*
  * POSIX: due semafori per un buffer implicito da 1 elemento — altrimenti il
  * producer può fare molti sem_post prima che il consumer legga e payload
  * resterebbe solo l’ultimo valore. g_slot_free=1 all’inizio: c’è posto per la
  * prima scrittura; dopo ogni lettura il consumer lo riposta a 1.
  */
 typedef struct {
     int payload;
     int __mn_p1_answer;
     pthread_mutex_t g_cs;
     sem_t g_slot_free;
     sem_t g_data_ready;
 } mps_t;
 
 static inline void init_mutexes(mps_t *m) {
     pthread_mutex_init(&m->g_cs, NULL);
     sem_init(&m->g_slot_free, 0, 1);
     sem_init(&m->g_data_ready, 0, 0);
 }
 
 static inline void destroy_mutexes(mps_t *m) {
     pthread_mutex_destroy(&m->g_cs);
     sem_destroy(&m->g_slot_free);
     sem_destroy(&m->g_data_ready);
 }
 
 static inline void ssend(mps_t *m, int msg) {
     sem_wait(&m->g_slot_free);
     pthread_mutex_lock(&m->g_cs);
     m->payload = msg;
     pthread_mutex_unlock(&m->g_cs);
     sem_post(&m->g_data_ready);
 }
 
 static inline void srecv(mps_t *m, int *answer) {
     sem_wait(&m->g_data_ready);
     pthread_mutex_lock(&m->g_cs);
     *answer = m->payload;
     pthread_mutex_unlock(&m->g_cs);
     sem_post(&m->g_slot_free);
 }
 #endif
 
 #ifndef MNEMO
 
 typedef struct { void (*fn)(mps_t *);        mps_t *mps;              } _mps_args_a;
 typedef struct { void (*fn)(mps_t *, int *); mps_t *mps; int *answer; } _mps_args_b;
 
 static void *_mps_run_a(void *arg) {
     _mps_args_a *a = (_mps_args_a *)arg; a->fn(a->mps); return NULL;
 }
 static void *_mps_run_b(void *arg) {
     _mps_args_b *b = (_mps_args_b *)arg; b->fn(b->mps, b->answer); return NULL;
 }
 
 static inline void mnemo_pthread_parallel2(
     void (*a)(mps_t *, int),
     void (*b)(mps_t *, int),
     mps_t *arg_a,
     mps_t *arg_b,
     int   *answer_b)
 {
     pthread_t ta, tb;
     _mps_args_a aa = { (void (*)(mps_t *))       a, arg_a           };
     _mps_args_b ba = { (void (*)(mps_t *, int *))b, arg_b, answer_b };
     pthread_create(&ta, NULL, _mps_run_a, &aa);
     pthread_create(&tb, NULL, _mps_run_b, &ba);
    pthread_join(ta, NULL);
    pthread_join(tb, NULL);
 }

 /*
  * Due canali mps per worker (richiesta + risposta), es. pi_calculus.c.
  * Non sostituisce mnemo_pthread_parallel2 usato da PC.c (un solo mps_t* per thread).
  */
 typedef struct {
     void (*fn)(mps_t *, mps_t *);
     mps_t *req;
     mps_t *resp;
 } _mps_rr_server_arg;

 static void *_mps_rr_server_run(void *arg) {
     _mps_rr_server_arg *a = (_mps_rr_server_arg *)arg;
     a->fn(a->req, a->resp);
     return NULL;
 }

 typedef struct {
     void (*fn)(mps_t *, mps_t *, int *);
     mps_t *req;
     mps_t *resp;
     int *answer;
 } _mps_rr_client_arg;

 static void *_mps_rr_client_run(void *arg) {
     _mps_rr_client_arg *a = (_mps_rr_client_arg *)arg;
     a->fn(a->req, a->resp, a->answer);
     return NULL;
 }

 static inline void mnemo_pthread_parallel2_rq(
     void (*server_fn)(mps_t *, mps_t *),
     void (*client_fn)(mps_t *, mps_t *, int *),
     mps_t *s_req,
     mps_t *s_resp,
     mps_t *c_req,
     mps_t *c_resp,
     int *answer)
 {
     pthread_t ta, tb;
     _mps_rr_server_arg sa = { server_fn, s_req, s_resp };
     _mps_rr_client_arg ca = { client_fn, c_req, c_resp, answer };
     pthread_create(&ta, NULL, _mps_rr_server_run, &sa);
     pthread_create(&tb, NULL, _mps_rr_client_run, &ca);
     pthread_join(ta, NULL);
     pthread_join(tb, NULL);
 }
 
 #endif /* !MNEMO */
 
 #endif /* MPS_H */