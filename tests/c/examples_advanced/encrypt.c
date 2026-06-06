void keyschedule(int key, int *s0, int *s1, int *s2, int *s3) {
    *s0 = key & 0xFF;
    *s1 = (*s0 * 17 + 13) & 0xFF;
    *s2 = (*s1 * 17 + 13) & 0xFF;
    *s3 = (*s2 * 17 + 13) & 0xFF;
}

int encrypt(int L, int R, int key) {
    int s0, s1, s2, s3, tmp;
    keyschedule(key, &s0, &s1, &s2, &s3);

    tmp = R; R = L ^ ((R ^ s0) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s1) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s2) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s3) * 3 & 0xFF); L = tmp;

    return (L << 8) | (R & 0xFF);
}

int decrypt(int cipher, int key) {
    int s0, s1, s2, s3, tmp;
    int L = (cipher >> 8) & 0xFF;
    int R = cipher & 0xFF;
    keyschedule(key, &s0, &s1, &s2, &s3);

    tmp = L; L = R ^ ((L ^ s3) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s2) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s1) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s0) * 3 & 0xFF); R = tmp;

    return (L << 8) | (R & 0xFF);
}

int main(void) {
    int cipher = encrypt(22, 10, 42);
    int plain  = decrypt(cipher, 42);

    printf("cipher: %d\n", cipher);
    printf("L: %d  R: %d\n", (plain >> 8) & 0xFF, plain & 0xFF);
    return 0;
}