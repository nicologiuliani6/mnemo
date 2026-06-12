// try/rollback Mnemo — ramo ROLLBACK (condizione falsa → undo body + rollback).
// mnemo-main-argc: 0
int main(void) {
    int x = 0;
    try (x == 7) {
        x += 5;
    } rollback {
        x += 99;
    }
    return x;            // atteso: 99 (body annullato x->0, poi rollback +99)
}
