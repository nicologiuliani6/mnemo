/*
 * mnemo_sync_print.h — printf serializzato tra thread (mutex dedicato)
 *
 * Usa un mutex separato da quelli in mps_t (g_cs / g_slot_free / g_data_ready):
 * non mischiare
 * la stampa con il protocollo ssend/srecv sullo stesso lock.
 *
 * Mnemo (VM):
 *   In un solo file .c, prima di #include, definire lo storage:
 *     #define MNEMO_SYNC_PRINT_DEFINE_MUTEX
 *     #include "mnemo_sync_print.h"
 *
 *   Prima dei thread: mnemo_sync_print_setup();
 *   Dopo join:        mnemo_sync_print_teardown();
 *   Stampa:           printf("fmt", args...) — ridefinito qui come stampa serializzata;
 *                     oppure MNEMO_SYNC_PRINTF(...) (stesso effetto).
 *
 * gcc nativo:
 *   Stesso schema; con più .c, solo una TU deve definire MNEMO_SYNC_PRINT_DEFINE_MUTEX
 *   e le altre includono l'header senza la define.
 */

#ifndef MNEMO_SYNC_PRINT_H
#define MNEMO_SYNC_PRINT_H

#ifdef MNEMO
/* Niente stdio.h: con -DMNEMO il preprocessore GCC include stdarg.h e il parse fallisce. */
typedef int pthread_mutex_t;
int pthread_mutex_init(pthread_mutex_t *m, void *attr);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);
#else
#include <pthread.h>
#include <stdio.h>
#endif

#ifdef MNEMO_SYNC_PRINT_DEFINE_MUTEX
pthread_mutex_t mnemo_sync_print_mutex;
#undef MNEMO_SYNC_PRINT_DEFINE_MUTEX
#else
extern pthread_mutex_t mnemo_sync_print_mutex;
#endif

static inline void mnemo_sync_print_setup(void) {
    pthread_mutex_init(&mnemo_sync_print_mutex, 0);
}

static inline void mnemo_sync_print_teardown(void) {
    pthread_mutex_destroy(&mnemo_sync_print_mutex);
}

#define MNEMO_SYNC_PRINTF(...)                    \
    do {                                          \
        pthread_mutex_lock(&mnemo_sync_print_mutex);   \
        (printf)(__VA_ARGS__);                    \
        pthread_mutex_unlock(&mnemo_sync_print_mutex); \
    } while (0)

#define printf(...) MNEMO_SYNC_PRINTF(__VA_ARGS__)

#endif /* MNEMO_SYNC_PRINT_H */
