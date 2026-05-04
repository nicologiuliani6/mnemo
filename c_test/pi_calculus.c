/*
 * π-calcolo: tupla <msg, canale_risposta> sul canale di richiesta.
 * Solo Mnemo. `req` è locale a main e passato a server/client.
 *
 * `ssend` / `srecv`: come naming mps.h — 2 argomenti sul canale di sola risposta,
 * 3 argomenti sulla richiesta (msg + canale di risposta nel payload).
 */

#ifndef MNEMO
#error "pi_calculus.c: usare solo con Mnemo (`mnemo run`). Nessun backend gcc qui."
#endif

typedef int mnemo_kairos_channel_t;

void mnemo_pi_ssend_request(
    mnemo_kairos_channel_t *lane, int msg, mnemo_kairos_channel_t *return_path);
void mnemo_pi_srecv_request(
    mnemo_kairos_channel_t *lane,
    int *msg_out,
    mnemo_kairos_channel_t *return_path_out);
void mnemo_pi_ssend_reply(mnemo_kairos_channel_t *reply_lane, int msg);
void mnemo_pi_srecv_reply(mnemo_kairos_channel_t *reply_lane, int *msg_out);

#define MN_GLUE(a, b) MN_GLUEI(a, b)
#define MN_GLUEI(a, b) a##b
#define MN_PP_ARGN(a1, a2, a3, n, ...) n
#define MN_PP_NARG(...) MN_PP_ARGN(__VA_ARGS__, 3, 2, 1)

#define ssend(...) MN_GLUE(ssend, MN_PP_NARG(__VA_ARGS__))(__VA_ARGS__)
#define ssend2(ch, msg) mnemo_pi_ssend_reply(&(ch), (msg))
#define ssend3(ch, msg, reply_ch) mnemo_pi_ssend_request(&(ch), (msg), &(reply_ch))

#define srecv(...) MN_GLUE(srecv, MN_PP_NARG(__VA_ARGS__))(__VA_ARGS__)
#define srecv2(ch, msgp) mnemo_pi_srecv_reply(&(ch), (msgp))
#define srecv3(ch, msgp, replyp) mnemo_pi_srecv_request(&(ch), (msgp), (replyp))

void mnemo_pthread_parallel2(
    void (*)(mnemo_kairos_channel_t),
    void (*)(mnemo_kairos_channel_t, int *),
    mnemo_kairos_channel_t *,
    mnemo_kairos_channel_t *,
    int *);

void server(mnemo_kairos_channel_t req) {
    int msg;
    mnemo_kairos_channel_t return_path; //non serve inizializzazione
    srecv(req, &msg, &return_path);
    msg = msg + 1;
    ssend(return_path, msg);
}

void client(mnemo_kairos_channel_t req, int *msg_out) {
    int msg;
    mnemo_kairos_channel_t return_path;

    msg = *msg_out;
    ssend(req, msg, return_path);
    srecv(return_path, &msg);
    *msg_out = msg;
}

int main(void) {
    mnemo_kairos_channel_t req;
    int msg = 10;
    mnemo_pthread_parallel2(server, client, &req, &req, &msg);
    return msg;
}
