void *malloc(int n);
void free(void *p);

int main(int argc, char **argv){
    int *p = malloc(sizeof(int));
    *p = argc;
    free(p);
    return 0;
}