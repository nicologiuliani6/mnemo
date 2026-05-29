#include <stdio.h>
#include <string.h>

int main(void) {
    printf("%d\n", strncmp("hello", "hello", 5));     /* 0 */
    printf("%d\n", strncmp("hello", "help", 3));      /* 0 */
    printf("%d\n", strncmp("hello", "help", 4));      /* <0 */
    printf("%d\n", strncmp("hello", "abc", 3));       /* >0 */
    printf("%d\n", strncmp("abc", "abcd", 5));        /* <0 */
    printf("%d\n", strncmp("abc", "abcd", 3));        /* 0 */
    return 0;
}
