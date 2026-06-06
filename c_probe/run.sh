#!/usr/bin/env bash
# gcc-vs-mnemo 1:1 diff harness. Usage: ./run.sh [dir]
# Skips files with `// SKIP` first line. Reports MISMATCH/ERR/PASS.
set -u
ROOT=/home/nico/Desktop/mnemo
DIR="${1:-$ROOT/c_probe/t}"
MN="$ROOT/.venv/bin/mnemo"
pass=0; fail=0; err=0
fails=""
for f in "$DIR"/*.c; do
  [ -e "$f" ] || continue
  head -1 "$f" | grep -q "// SKIP" && continue
  g=$(gcc -std=c11 -w "$f" -o /tmp/__g 2>/tmp/__gcc_err)
  if [ $? -ne 0 ]; then echo "GCCFAIL $(basename $f)"; err=$((err+1)); continue; fi
  gout=$(/tmp/__g 2>/dev/null); gcode=$?
  # Una sola invocazione (raddoppiava il tempo). --native-arith è 1:1 con
  # l'interprete puro (mul/div/bit O(1) in C) → niente timeout-flakiness su
  # programmi arith/bit-heavy (bm_count_bits, p6_endian_swap, pd_long_arith, …).
  mraw=$(timeout 120 "$MN" run "$f" --native-arith 2>/tmp/__mn_err)
  mout=$(echo "$mraw" | grep -v "__mn_exit")
  if echo "$mout" | grep -q "^mnemo:"; then
     echo "MNERR  $(basename $f): $(echo "$mout"|head -1)"; err=$((err+1)); fails="$fails $(basename $f)"; continue
  fi
  if [ "$gout" != "$mout" ]; then
     echo "MISMATCH $(basename $f)"; echo "  gcc:[$gout]"; echo "  mn :[$mout]"; fail=$((fail+1)); fails="$fails $(basename $f)"; continue
  fi
  pass=$((pass+1))
done
echo "----"
echo "PASS=$pass MISMATCH=$fail ERR=$err"
[ -n "$fails" ] && echo "FAILS:$fails"
