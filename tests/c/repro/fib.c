/* fib parallelo: PAR solo al top-level (main); ricorsione interna sequenziale.
 * Pattern stesso di c_examples/ex33_parallel2_fib.c — evita esplosione thread O(2^n)
 * di parallel2(f,f,…) annidato in f stesso. Mnemo lower `par … and … rap` al top
 * (due worker distinti fib_left/fib_right), Mnemo memory partition 2·S.
 */

void mnemo_pthread_parallel2(void (*a)(int), void (*b)(int), int arg_a, int arg_b);

int fibonacci(int n);

int rl;
int __mn_p1_rr;

void fib_left(int n)  { rl = fibonacci(n); }
void fib_right(int n) { __mn_p1_rr = fibonacci(n); }

int main(void){
    mnemo_pthread_parallel2(fib_left, fib_right, 9, 8);
    return rl + __mn_p1_rr; /* fib(10) = 55 + 34 = 89 */
}

int fibonacci(int n) {
    if (n <= 1) {
        return 1;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
