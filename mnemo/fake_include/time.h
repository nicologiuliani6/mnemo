/* Mnemo fake time.h: VM no clock/timer. time/clock ritornano 0. */
#ifndef _MNEMO_TIME_H
#define _MNEMO_TIME_H

typedef long time_t;
typedef long clock_t;

#define CLOCKS_PER_SEC 1000000

time_t  time (time_t *t);
clock_t clock(void);

#endif
