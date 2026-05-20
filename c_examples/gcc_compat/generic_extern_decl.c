/* `extern T g;` forward + definition stesso file. Mnemo skippa la forward decl. */
#include <stdio.h>

extern int counter;
extern int multiplier;

int read_state(void) { return counter * multiplier; }

int counter = 7;
int multiplier = 3;

int main(void) {
    int r = read_state();
    printf("%d\n", r);
    return r;
}
