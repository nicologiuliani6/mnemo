/*
 * parallel2 a 4 argomenti: void worker(int n), argomenti per regione 0 e 1.
 * (La forma a 2 argomenti resta: void worker(void).)
 */

void mnemo_pthread_parallel2(void (*a)(int), void (*b)(int), int arg_a, int arg_b);

int fibonacci(int n);

int rl;
int __mn_p1_rr;

void fib_left(int n) { rl = fibonacci(n); }

void fib_right(int n) { __mn_p1_rr = fibonacci(n); }

int main(void) {
    mnemo_pthread_parallel2(fib_left, fib_right, 7, 8);
    return rl + __mn_p1_rr; //fib(9) = 55
}

int fibonacci(int n) {
    if (n <= 1) {
        return 1;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
