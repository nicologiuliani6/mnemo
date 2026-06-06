/* Letterali char con tutti gli escape C: `\n`, `\t`, `\r`, `\v`,
   `\f`, `\a`, `\b`, `\0`, `\\`, `\'`, `\"`, `\?` (trigraph guard),
   `\xHH`. */
#include <stdio.h>

int main(void) {
    char n  = '\n';   /* 10 */
    char t  = '\t';   /* 9 */
    char r  = '\r';   /* 13 */
    char v  = '\v';   /* 11 */
    char f  = '\f';   /* 12 */
    char a  = '\a';   /* 7 */
    char b  = '\b';   /* 8 */
    char z  = '\0';   /* 0 */
    char bs = '\\';   /* 92 */
    char sq = '\'';   /* 39 */
    char dq = '\"';   /* 34 */
    char qm = '\?';   /* 63 */
    char hx = '\x41'; /* 65 */
    printf("%d %d %d %d %d %d %d %d %d %d %d %d %d\n",
           n, t, r, v, f, a, b, z, bs, sq, dq, qm, hx);
    return n + t + qm;
}
