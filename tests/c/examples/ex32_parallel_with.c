/*
 * Modello: main ≈ new_thread(worker, …); corpo_main
 * → Kairos: par call worker … and call corpo … rap
 *
 * mnemo_pthread_parallel_with(worker, corpo)
 * mnemo_pthread_parallel_with1(worker, arg, corpo)
 *
 * Il corpo va estratto in void corpo(void). rap = join su entrambi i rami.
 */

void mnemo_pthread_parallel_with(void (*worker)(void), void (*cont)(void));
void mnemo_pthread_parallel_with1(void (*worker)(void), int arg, void (*cont)(void));

void worker_side(void) {}

void main_tail(void) {}

int main(void) {
    mnemo_pthread_parallel_with(worker_side, main_tail);
    return 0;
}
