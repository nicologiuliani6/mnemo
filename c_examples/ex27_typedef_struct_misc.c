/* typedef, struct a campi scalari, (void)expr, parametro int a[N] (decay). */
typedef unsigned int uint;

struct Point {
  int x;
  int y;
};

void use_array_param(int a[4]) {
  (void)a;
}

int main(void) {
  uint u = 5;
  struct Point p;
  p.x = 10;
  p.y = 20;
  (void)u;
  use_array_param(0);
  return p.x + p.y + sizeof(struct Point) + sizeof(uint);
}
