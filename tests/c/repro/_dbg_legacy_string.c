#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <strings.h>

int main(void) {
    /* strcasecmp / strncasecmp */
    printf("%d\n", strcasecmp("HELLO", "hello"));
    printf("%d\n", strcasecmp("abc", "abd"));
    printf("%d\n", strncasecmp("HELLO", "help", 3));
    printf("%d\n", strncasecmp("HELLO", "help", 4));

    /* index / rindex (alias di strchr/strrchr) */
    const char *p = index("hello", 'l');
    const char *q = rindex("hello", 'l');
    if (p) printf("p=%s\n", p);
    if (q) printf("q=%s\n", q);

    /* bzero / bcopy */
    char a[10] = "garbage";
    bzero(a, 10);
    a[0] = 'X';
    printf("a=%c\n", a[0]);

    char src[] = "abcd";
    char dst[10] = "00000000";
    bcopy(src, dst, 4);
    dst[4] = 0;
    printf("dst=%s\n", dst);

    return 0;
}
