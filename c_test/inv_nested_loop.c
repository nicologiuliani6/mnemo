// REGRESSION GUARD (RISOLTO Kairos 79ab8fe): ora inverte sotto
// --check-invertibility. Era SIGSEGV (use-after-free in exec_branch_inverse:
// blanket restore vars[]=saved reinstaurava Var* liberati da op_local/
// op_delocal nella recursion annidata dei loop). Fix: restore solo slot param.
int main(void){ int i=0,j,s=0; while(i<3){ j=0; while(j<3){ s+=j; j++; } i++; } return s; }
