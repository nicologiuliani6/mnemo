int main(void) {
    int L = 22;
    int R = 10;
    int key = 42;
    int s0 = key & 0xFF;
    int s1 = (key * 17 + 13) & 0xFF;
    int s2 = (s1  * 17 + 13) & 0xFF;
    int s3 = (s2  * 17 + 13) & 0xFF;
    int tmp;

    /* encrypt - 4 round feistel con permutazione */
    tmp = R; R = L ^ ((R ^ s0) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s1) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s2) * 3 & 0xFF); L = tmp;
    tmp = R; R = L ^ ((R ^ s3) * 3 & 0xFF); L = tmp;

    /* decrypt - round inversi */
    tmp = L; L = R ^ ((L ^ s3) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s2) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s1) * 3 & 0xFF); R = tmp;
    tmp = L; L = R ^ ((L ^ s0) * 3 & 0xFF); R = tmp;

    return (L ^ 22) | (R ^ 10);
}