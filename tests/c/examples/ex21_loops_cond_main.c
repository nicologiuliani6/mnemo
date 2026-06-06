// mnemo-main-argc: 4

int side(int x) {
    return x;
}

int main(int argc, char **argv) {
    int i;
    int s;
    int t;
    s = 0;
    t = side(argc);
    for (i = 0; i < 3; i++) {
        if (i == 1) {
            continue;
        }
        s += i;
    }
    if (t == 4 && argc > 0) {
        s += 10;
    }
    i = 0;
    while (i < 5) {
        i += 1;
        if (i == 4) {
            break;
        }
    }
    return 0;
}
