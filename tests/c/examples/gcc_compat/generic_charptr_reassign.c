#include <stdio.h>

int main(void) {
    const char *n;
    int k = 2;

    if (k == 1)      n = "one";
    else if (k == 2) n = "two";
    else             n = "other";
    printf("%s\n", n);

    for (int i = 0; i < 3; i++) {
        const char *m;
        switch (i) {
            case 0:  m = "zero"; break;
            case 1:  m = "uno";  break;
            default: m = "due";  break;
        }
        printf("%s\n", m);
    }

    const char *d;
    d = "direct";
    printf("%s\n", d);
    return 0;
}
