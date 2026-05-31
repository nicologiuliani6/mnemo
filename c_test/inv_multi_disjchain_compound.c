// --check-invertibility FAIL: POP stack vuoto inv=1.
// >=3 disj-chain store + compound read g[a]+=g[b] (legge 2, scrive 1).
// Indipendente dal nesting (fallisce anche con indici 0/1). Bug hist
// cumulativo READ vs WRITE disj-chain. Vedi TODO.md.
int g[6];
int main(void){ int a=0,b=1,c=0; g[a]=10; g[b]=20; g[c]=30; g[a]+=g[b]; return g[0]; }
