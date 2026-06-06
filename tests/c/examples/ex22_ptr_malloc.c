// Pool puntatori: malloc / *p / free (lib ptr_pool.kairos)

void *malloc(int n);
void free(void *p);

int main(void) {
    int *p;
    p = (void *)malloc(4);
    *p = 42;
    int x;
    x = *p;
    free((void *)p);
    return 0;
}
