/* Array di puntatori a funzione con indice RUNTIME: dispatch a chain. */
#include <stdio.h>

int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }

void hello(int n) { printf("hello %d\n", n); }
void world(int n) { printf("world %d\n", n); }

int main(void) {
    int (*ops[3])(int, int) = {add, sub, mul};
    for (int i = 0; i < 3; i++)
        printf("%d\n", ops[i](10, 3));

    void (*greet[2])(int) = {hello, world};
    for (int i = 0; i < 2; i++)
        greet[i](i * 10);

    int s = 0;
    int j = 1;
    s += ops[j](100, 7);
    printf("s=%d\n", s);
    return 0;
}
