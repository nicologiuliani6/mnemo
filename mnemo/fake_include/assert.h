#ifndef _MNEMO_ASSERT_H
#define _MNEMO_ASSERT_H

/* In Mnemo non c'è abort/stderr/syscall: assert è no-op in build,
   come `-DNDEBUG`. Le asserzioni di runtime sui valori sono incompatibili
   col modello reversibile (terminazione non recuperabile). */

#define assert(expr) ((void)0)
#define static_assert(expr, msg) _Static_assert(expr, msg)

#endif
