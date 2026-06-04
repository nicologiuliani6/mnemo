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
  mout=$(timeout 60 "$MN" run "$f" 2>/tmp/__mn_err | grep -v "__mn_exit"); 
  mcode=$(timeout 60 "$MN" run "$f" 2>/dev/null | grep "__mn_exit" | sed 's/.*__mn_exit://')
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
