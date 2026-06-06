// REGRESSION GUARD (RISOLTO Kairos c5b56ae): ora inverte sotto
// --check-invertibility. Era POP stack vuoto: >=3 disj-chain store +
// compound g[a]+=g[b] = 36 nested IF > vecchio MAX_IFS=32 → collect_ifs
// troncava la IF-map. Fix: MAX_IFS->256. Vedi TODO.md.
int g[6];
int main(void){ int a=0,b=1,c=0; g[a]=10; g[b]=20; g[c]=30; g[a]+=g[b]; return g[0]; }
