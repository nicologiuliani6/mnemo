/* sizeof risolto a compile-time → costante Kairos. */
int main(void) {
    int x = 0;
    x += sizeof(int);
    x += sizeof(x);
    x += sizeof(int *);
    return 0;
}
