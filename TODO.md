Cosa i log hanno chiarito
__mn_move_int non era il problema — l’inversione termina con loc_sz: -1 (stack locale vuota). Il panic END_PROC: variabili LOCAL non chiuse su main veniva da a/r non delocalati nel test (falso allarme).

qf = -1 — il corpo del loop from q == 0 veniva invertito una volta anche quando saved_r < b (nessuna iterazione forward), con PUSHEQ q 1 → q = -1 propagato su qf.

Progresso su encrypt (dopo fix mirati):

prima: deadlock / qf = -1
poi: saved_r = 1 (guardia che saltava anche PUSHEQ saved_r r)
poi: i = -1
ora: t = -255 in __mn_bit_k_signed (catena annidata floor_div2 → divmod → move_int)
Fix applicati (kairos + mnemo)
invert_if_entry_lval: legge saved_r / ts dalla copia locale, non da a/t già azzerati da move_int
Guardie loop: non invertire MINEQ r / PUSHEQ q se saved_r < b; non peelare from q==0 in quel caso
lib/bits.kairos: snapshot ts per if ts >= 0 + ordine LIFO delocal corretto
Test kairos: delocal su main con valori attesi dopo uncall
Stato test
Test	Esito
test_move_int_uncall.kairos
OK
test_divmod_uncall.kairos
OK
encrypt.c --opt-uncall-user-calls
ancora exit 1 (t = -255 in __mn_bit_k_signed)
Il deadlock è risolto; resta da stabilizzare l’uncall sulla catena floor_div2 / bit_k (stesso schema: loop/IF saltati in avanti ma ancora toccati in inversa).

DA FARE: te devi fixare tutto. STEP su come ffixare: creati dei file in .c o in .kairos semplici e vedi cosa VA e cosa non va CON --opt-uncall-user-calls. CAPISCI COSA NON VA, e poi fixi in Mnemo o kairos, riparti da 0 riprovando tutto e continua finche tutto non va. ATTENZIONA ALLA TRADUZIONE MNEMO->KAIROS fra il call e uncall . PS: @c_test/loop.c la versione ottimizzata di loop va mentre quella di @c_test/encrypt.c non va. Quindi guarde le differenze nelle due tarduzioni