// try/rollback Mnemo — ramo COMMIT (condizione vera → il body resta).
// mnemo-main-argc: 0
int main(void) {
    int x = 0;
    try (x == 5) {
        x += 5;
    } rollback {
        x += 99;
    }
    return x;            // atteso: 5
}
