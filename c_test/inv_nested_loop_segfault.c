// --check-invertibility SIGSEGV (exit -11). Nested loop inverse (from/until
// annidati). Indipendente da array/disj-chain. Bug distinto. Vedi TODO.md.
int main(void){ int i=0,j,s=0; while(i<3){ j=0; while(j<3){ s+=j; j++; } i++; } return s; }
