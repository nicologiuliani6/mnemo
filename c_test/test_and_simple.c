// Test: funzione con & senza annidamento
int and_fn(int a) {
    return a & 255;
}
int main(void) {
    int r = and_fn(42);
    return 0;
}
