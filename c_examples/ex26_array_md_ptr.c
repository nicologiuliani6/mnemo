/* Multidim, unsigned/bool, array di puntatori. */
int main(void) {
    int m[2][3];
    unsigned u[2];
    unsigned int z[2];
    _Bool flags[2];
    int *p[2];
    void *v[1];
    int g[2][2] = { { 1, 2 }, { 3, 4 } };

    m[0][0] = g[0][0];
    m[1][2] = g[1][1];
    u[0] = 3;
    u[1] = 4;
    flags[0] = 1;
    flags[1] = 0;
    z[0] = 10;
    z[1] = 11;
    p[0] = (void *)0;
    p[1] = (void *)0;
    v[0] = (void *)0;
    return 0;
}
