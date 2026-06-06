/* switch su char con `case 'x':` letterali char (e fall-through). */
#include <stdio.h>

int classify(char c) {
    int r;
    switch (c) {
        case 'a': case 'e': case 'i': case 'o': case 'u':
            r = 1; break;
        case 'A': case 'E': case 'I': case 'O': case 'U':
            r = 2; break;
        case ' ': case '\t': case '\n':
            r = 3; break;
        case '0': case '1': case '2': case '3': case '4':
        case '5': case '6': case '7': case '8': case '9':
            r = 4; break;
        default:
            r = 0;
    }
    return r;
}

int main(void) {
    int s = 0;
    s += classify('e');   /* 1 */
    s += classify('Z');   /* 0 */
    s += classify(' ');   /* 3 */
    s += classify('7');   /* 4 */
    s += classify('!');   /* 0 */
    printf("%d\n", s);
    return s;
}
