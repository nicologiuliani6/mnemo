int main(void) {
    int k;
    int r;
    k = 2;
    r = 0;
    switch (k) {
        case 1:
            r = r + 1;
            break;
        case 2:
            r = r + 5;
            break;
        default:
            r = r + 9;
            break;
    }
    return 0;
}
