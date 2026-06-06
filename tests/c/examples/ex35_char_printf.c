// mnemo-main-argc: 0
/*
 * Output atteso (tre righe, poi opz. «=== VM dump ===» se lanci solo la VM Kairos):
 *   a
 *   % Z 108
 *   !
 * Se dopo «a» manca il \\n, il %% del secondo printf resta sulla stessa riga (a% Z 108).
 */
int main(void) {
    char c = 'a';
    printf("%c\n", c);
    printf("%% %c %d\n", 'Z', 108);
    char *msg = "!\n";
    printf("%s", msg);
    return 0;
}
