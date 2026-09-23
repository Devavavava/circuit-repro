#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# gf180mcu + ngspice: run-to-run DC variation demo
#
# Shows that a SINGLE gf180 transistor's DC operating point changes every run
# with byte-identical input -- because the gf180 statistical models default to
# Monte-Carlo process/mismatch variation ON (sw_stat_global=1, sw_stat_mismatch=1
# in design.ngspice). Turning those switches OFF makes it fully deterministic.
#
# This is EXPECTED model behaviour, not an ngspice defect. The point of the demo
# is to (a) see the variation, and (b) confirm the one-line fix.
#
# Prereqs:
#   - ngspice (any recent build; tested on ngspice-47)  -> set $NGSPICE or PATH
#   - the open-source gf180mcu PDK ngspice models        -> set $GF180_MODELS
#     (dir containing design.ngspice + sm141064.ngspice; Apache-2.0)
#     https://github.com/google/gf180mcu-pdk
#
# Usage:  ./run_demo.sh [N_runs]
# ---------------------------------------------------------------------------
set -u
N="${1:-12}"
NG="${NGSPICE:-$(command -v ngspice)}"
GF="${GF180_MODELS:-/home/dpatni/circuit-repro/.env/pdks/gf180mcu/models/ngspice}"
INC="$GF/design.ngspice"
LIB="$GF/sm141064.ngspice"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

if [ ! -x "$NG" ] && ! command -v "$NG" >/dev/null 2>&1; then
  echo "ngspice not found; set \$NGSPICE"; exit 1; fi
for f in "$INC" "$LIB"; do
  [ -f "$f" ] || { echo "missing gf180 model file: $f  (set \$GF180_MODELS)"; exit 1; }; done

echo "ngspice : $("$NG" --version 2>/dev/null | grep -oiE 'ngspice-[0-9]+' | head -1)"
echo "models  : $GF"
echo "runs    : $N   (single nmos_3p3, W=10u L=0.3u, plain .op)"
echo

# write the two decks: identical except the MC switches
mkdeck () { # $1 = extra .param line ; $2 = outfile
  cat > "$2" <<EOF
* gf180 single-device DC determinism demo
.include "$INC"
.lib "$LIB" typical
$1
Vg g 0 dc 1.2
Vd d 0 dc 1.8
XM1 d g 0 0 nmos_3p3 w=10u l=0.3u nf=5
.control
op
print @m.xm1.m0[id]
.endc
.end
EOF
}
mkdeck ""                                            "$WORK/on.cir"   # MC default = ON
mkdeck ".param sw_stat_global=0 sw_stat_mismatch=0"  "$WORK/off.cir"  # MC OFF
mkdeck ".option seed=12345"                          "$WORK/seed.cir" # MC ON + fixed seed

collect () { # $1 = deck ; echoes N id values (amps)
  for _ in $(seq 1 "$N"); do
    OMP_NUM_THREADS=1 "$NG" -b "$1" 2>/dev/null \
      | grep -iE 'id]\s*=' | head -1 | awk '{print $NF}'
  done
}
ON="$(collect "$WORK/on.cir")"
OFF="$(collect "$WORK/off.cir")"
SEED="$(collect "$WORK/seed.cir")"

# --- stats + ASCII "window" ------------------------------------------------
report () { # $1 = label ; $2 = newline-separated values
  local label="$1" vals="$2"
  echo "===== $label ====="
  local n_distinct min max
  n_distinct=$(printf '%s\n' "$vals" | sort -u | grep -c .)
  min=$(printf '%s\n' "$vals" | sort -g | head -1)
  max=$(printf '%s\n' "$vals" | sort -g | tail -1)
  printf '%s\n' "$vals" | nl -w2 -s': ' | sed 's/^/  run /'
  awk -v mn="$min" -v mx="$max" -v nd="$n_distinct" -v n="$N" 'BEGIN{
    rng=mx-mn; rel=(mx>0)?100*rng/((mn+mx)/2):0;
    printf "  distinct values: %d/%d   min=%.6e  max=%.6e  spread=%.3f%%\n", nd,n,mn,mx,rel;
  }'
  # ASCII strip: map each value onto a 50-col axis [min,max]
  echo "  DC(id) axis  [min .......................................... max]"
  printf '%s\n' "$vals" | awk -v mn="$min" -v mx="$max" '{
    w=50; rng=mx-mn; c=(rng>0)?int((($1-mn)/rng)*w):0;
    s="  |"; for(i=0;i<w;i++) s=s (i==c?"#":"-"); print s "|";
  }'
  echo
}
report "MC ON  (gf180 default: sw_stat_global=1, sw_stat_mismatch=1)"  "$ON"
report "MC OFF (sw_stat_global=0, sw_stat_mismatch=0)"                 "$OFF"
report "MC ON + .option seed=12345 (reproducible corner)"             "$SEED"
echo "Interpretation:"
echo "  MC ON          -> scatters across the axis (fresh random Vth each run)"
echo "  MC OFF         -> single column (deterministic typical corner)  [fix for sizing]"
echo "  MC ON + seed   -> single column (ngspice honours .option seed; NOT a bug)"
echo
echo "Note: 'set rndseed=N' / 'setseed N' in .control do NOT fix it here;"
echo "      the deck-level '.option seed=N' does (it is parsed before model setup)."
