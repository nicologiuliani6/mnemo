/* enum, union, ternario, virgola, XOR, struct annidata, switch su enum, ^= su union */
enum Tx { Z = 0, ONE, TWO = 2 };
typedef enum { K = 15 } Alias;

union Num {
  int i;
  unsigned u;
};

struct Nest {
  int x;
  struct {
    int y;
  } inner;
};

void noop(int q) { (void)q; }

int main(void) {
  enum Tx e = ONE;
  union Num n;
  n.i = 7;
  Alias a = K;
  struct Nest s;
  s.x = 3;
  s.inner.y = 4;

  int tern = (e == ONE) ? 100 : 0;
  int com = (tern, a + 1);
  int xr = s.x ^ 8;
  n.i ^= 2;

  int sw = 0;
  switch (ONE) {
    case ONE:
      sw = 50;
      break;
    default:
      sw = 0;
      break;
  }

  noop(com);
  return tern + com + xr + sw + sizeof(union Num) + s.inner.y + TWO + n.i;
}
