int main(void) {
    int a;
    a = 1;
    {
        int t;
        t = 0;
        t = t + a;
        t = t + 4;
        a = a + t;
    }
    return 0;
}
