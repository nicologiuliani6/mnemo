void *malloc(int n);
void free(void *p);

int fibonacci(int n);

int main(int argc, char **argv){
    return fibonacci(argc);
}

int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
