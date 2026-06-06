/* getenv: VM no env, Mnemo AST rewrite a NULL. Match gcc se env var
   non settata. Test usa nome var improbabile per evitare divergenze. */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    const char *v = getenv("__MNEMO_UNLIKELY_ENV_VAR_XYZ123__");
    if (v == 0) {
        printf("null\n");
    } else {
        printf("set\n");
    }
    return 0;
}
