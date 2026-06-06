/*
 * mnemo_pthread_start / mnemo_pthread_start1 — un ramo par/rap nella VM Kairos.
 *
 * Non è pthread_create POSIX: il chiamante si blocca fino a fine worker (join).
 *
 * - mnemo_pthread_start(f)           → void f(void)
 * - mnemo_pthread_start1(f, expr)    → void f(T x) con un solo parametro scalare
 */
void mnemo_pthread_start(void (*f)(void));
void mnemo_pthread_start1(void (*f)(void), int arg);

void step(void) {}

void add_k(int k) { (void)k; }

int main(void) {
    mnemo_pthread_start(step);
    mnemo_pthread_start1(add_k, 7);
    return 0;
}
