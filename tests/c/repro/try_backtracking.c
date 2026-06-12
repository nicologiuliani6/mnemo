// Backtracking con try in un ciclo che chiama una funzione (no rollback:
// la mossa invalida viene solo annullata). budget=10, pesi 1..6.
// mnemo-main-argc: 0
void add_weight(int *load, int w) {
    *load += w;
}
int main(void) {
    int load = 0;
    int budget = 10;
    for (int i = 1; i <= 6; i++) {
        try (load <= budget) {
            add_weight(&load, i);
        }
    }
    return load;         // atteso: 10 (1+2+3+4; 5,6 sforano → backtrack)
}
