/*
 * π-calculus su Kairos: tuple su canale + channel passing (come negli esempi Kairos).
 *
 * Riferimenti (VM Kairos):
 *   examples/pi_calculus.kairos   — ssend(<msg, resp>, req), srecv(<msg, resp>, req)
 *   examples/example_login.kairos — pipeline con canale di risposta nel payload
 *
 * La VM accetta in ssend/srecv tuple di int, stack e channel; passando un channel
 * nel payload si ottiene lo stesso effetto di inviare un nome di canale (stile π).
 *
 * Su Mnemo questi simboli non sono funzioni C reali: il compilatore li abbassa a
 * istruzioni IR ISsend/ISrecv con payload multiplo. Richiede -DMNEMO.
 *
 * Limitazioni attuali (2026):
 *   - Solo `int` e `mnemo_kairos_channel_t` nelle tuple esposte da questa API.
 *   - `mnemo_kairos_channel_t` a livello file (o locale): niente struct C annidate.
 *   - Per gcc nativo non c’è ancora un runtime: usare .kairos a mano o mps.h.
 */

#ifndef MNEMO_KAIROS_PI_H
#define MNEMO_KAIROS_PI_H

#ifdef MNEMO

typedef int mnemo_kairos_channel_t;

/* ssend(<msg, *return_path>, *lane) — il server riceve con mnemo_pi_srecv_request */
void mnemo_pi_ssend_request(
    mnemo_kairos_channel_t *lane, int msg, mnemo_kairos_channel_t *return_path);

/* srecv(<*msg_out, *return_path_out>, *lane) */
void mnemo_pi_srecv_request(
    mnemo_kairos_channel_t *lane,
    int *msg_out,
    mnemo_kairos_channel_t *return_path_out);

/* ssend(<msg>, *reply_lane) */
void mnemo_pi_ssend_reply(mnemo_kairos_channel_t *reply_lane, int msg);

/* srecv(<*msg_out>, *reply_lane) */
void mnemo_pi_srecv_reply(mnemo_kairos_channel_t *reply_lane, int *msg_out);

#else

/* Placeholder: su host C usare gli esempi .kairos o mps.h per I/O sincrono. */
typedef void mnemo_kairos_channel_t;

#endif

#endif
