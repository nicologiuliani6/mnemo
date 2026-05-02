/* Array 1D: dichiarazione, init, indice costante e variabile. */
int main(void) {
    int a[4] = {10, 20, 30, 40};
    int i = 2;
    int x = 0;
    x += a[0];
    x += a[i];
    x += sizeof(a);
    x += sizeof(int[3]);
    a[1] = 7;
    return 0;
}
