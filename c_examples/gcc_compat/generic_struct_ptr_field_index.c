/* `s.ptr_field[i]` (r-value) e `s.ptr_field[i] = X` (l-value):
   rewrite a `*(s.ptr_field + i)`. */
#include <stdio.h>

struct Wrap { int hdr; int *data; int tail; };

int main(void) {
    int buf[5] = {1, 2, 3, 4, 5};
    struct Wrap w;
    w.hdr = 10;
    w.data = buf;
    w.tail = 99;
    int s = w.hdr + w.tail;
    for (int i = 0; i < 5; i++) s += w.data[i];
    /* l-value */
    w.data[0] = 100;
    w.data[4] = 500;
    printf("%d %d %d %d\n", s, buf[0], buf[4], w.tail);
    return s + buf[0] + buf[4];
}
