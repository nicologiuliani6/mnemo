int main(void) {
    int x;
    int y;
    x = 3;
    y = 0;
    if (x > 2) {
        y = y + 1;
    } else {
        y = y + 10;
    }
    while (x > 0) {
        x = x - 1;
        y = y + 1;
    }
    return 0;
}
