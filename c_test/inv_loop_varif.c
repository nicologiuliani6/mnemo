/* Regression guard: opt-uncall su loop con IF body data-variante.
 *
 * touch_idx_loop ha `for { if(G[i]==0) G[i]=... }`: la decisione dell'IF
 * varia tra iterazioni (G[0]=5 dopo bump → i=0 false, i=1/2 true). Sotto
 * --opt-uncall-user-calls l'inverse del from-loop falliva
 *   DELOCAL var=__mn_lc1 atteso=0 trovato=1
 * perché gli IF dentro il loop usavano la branch_trace globale (FIFO) che
 * non si allinea al peel inverso (reverse). Fix Kairos: line_inside_loop_body()
 * forza recompute per gli IF dentro un loop body. Era l'ultima esclusione
 * loop_hoist_targets, ora rimossa lato Mnemo. Run con --opt-uncall-user-calls. */
int G[3];

void bump(void) { G[0] += 5; }

void touch_idx_loop(void) {
    int i;
    for (i = 0; i < 3; i++) {
        if (G[i] == 0) {
            G[i] = i + 10;
        }
    }
}

int main(void) {
    G[0] = 0; G[1] = 0; G[2] = 0;
    bump();
    touch_idx_loop();
    return 0;
}
