/* FuncCall come condizione di if/while: `if (f(x)) …`. */
#include <stdio.h>

int is_vowel(char c) {
    return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
}

int square_gt(int x, int t) {
    return x * x > t;
}

int main(void) {
    char s[] = "hello world";
    int n_vowel = 0;
    for (int i = 0; s[i] != '\0'; i++)
        if (is_vowel(s[i])) n_vowel++;

    int big = 0;
    for (int i = 0; i < 10; i++)
        if (square_gt(i, 30)) big++;

    printf("%d %d\n", n_vowel, big);
    return n_vowel + big;
}
