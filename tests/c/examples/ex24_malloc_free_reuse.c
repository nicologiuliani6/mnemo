/* Due alloc, free dell'ultima, terza alloc riusa lo slot (ctr torna indietro). */
void *malloc(int n);
void free(void *p);

int main(void) {
    int *a = (int *)malloc(1);
    int *b = (int *)malloc(1);
    *a = 1;
    *b = 2;
    free((void *)b);
    int *c = (int *)malloc(1);
    *c = 3;
    free((void *)a);
    free((void *)c);
    return 0;
}
