/* Ritorno struct multi-parola (ABI __mn_ret0..), passaggio per valore, parametro struct. */
struct Pair {
  int a;
  int b;
};

struct Pair makePair(void) {
  struct Pair s;
  s.a = 7;
  s.b = 11;
  return s;
}

int sumPair(struct Pair t) {
  return t.a + t.b;
}

int main(void) {
  struct Pair x;
  x = makePair();
  return sumPair(x) + x.a + sumPair(makePair());
}
