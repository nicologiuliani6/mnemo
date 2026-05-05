void mnemo_pthread_parallel2(
    void (*a)(int, int *),
    void (*b)(int, int *),
    int arg_a,
    int arg_b,
    int *ret_a,
    int *ret_b
);

int fib(int n, int *ret){
    if(n <= 1){
        *ret += 1;
        return 1;
    }
    int ret1, ret2;
    mnemo_pthread_parallel2(fib, fib, n-1, &ret1, n-2,  &ret2);
    return ret1 + ret2;
}


int main(void){
    return fib(10, (int*)0);       
}