/* `memcpy(dst, src, N)` e `memset(dst, v, N)` espansi a compile-time
   quando dst (e src) sono array Mnemo e N è una costante. Mnemo non
   ha runtime memcpy/memset — solo questa forma static. */
#include <stdio.h>
#include <string.h>

int main(void) {
    /* memcpy tra int[] */
    int a[5] = {0};
    int b[5] = {1, 2, 3, 4, 5};
    memcpy(a, b, sizeof(b));
    printf("%d %d %d %d %d\n", a[0], a[1], a[2], a[3], a[4]);

    /* memset a 0 */
    memset(a, 0, sizeof(a));
    printf("%d %d %d %d %d\n", a[0], a[1], a[2], a[3], a[4]);

    /* memcpy parziale */
    int c[5] = {9, 9, 9, 9, 9};
    int d[3] = {7, 8, 6};
    memcpy(c, d, sizeof(d));
    printf("%d %d %d %d %d\n", c[0], c[1], c[2], c[3], c[4]);

    /* memcpy da literal su char[]: verifica byte-per-byte */
    char s[10] = {0};
    memcpy(s, "hello", 6);
    printf("%d %d %d %d %d %d\n",
           (int)s[0], (int)s[1], (int)s[2], (int)s[3], (int)s[4], (int)s[5]);

    return 0;
}
