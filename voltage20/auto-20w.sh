#!/bin/bash
# Launched by root launchd after OpenCore has loaded VoltageShift.kext.
# Applies 20W only when on AC power. Safe idempotent read-modify-write helper.
set -euo pipefail
BIN="/usr/local/libexec/matebook-pl1/voltageshift"
echo "[$(/bin/date)] Trying PL1=20W (AC power only)"

if [ "$(/usr/sbin/sysctl -n machdep.cpu.brand_string)" != "11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz" ]; then
  echo "PL1_20W_ERROR: CPU model mismatch; refusing to write."
  exit 10
fi
if ! /usr/bin/pmset -g batt | /usr/bin/grep -q "AC Power"; then
  echo "PL1_20W_SKIPPED: Battery operation, do not raise PL1."
  exit 0
fi
if [ ! -x "$BIN" ]; then
  echo "PL1_20W_ERROR: CLI not installed"
  exit 11
fi

for i in $(/usr/bin/seq 1 25); do
  if /usr/bin/kmutil showloaded 2>/dev/null | /usr/bin/grep -qi "VoltageShift"; then
    break
  fi
  /bin/sleep 2
done

OUT="$("$BIN" pl1-20w 2>&1)" || {
  echo "$OUT"
  echo "PL1_20W_ERROR: Cannot apply (Kext not loaded, MSR locked or write rejected)."
  exit 12
}
echo "$OUT"
echo "[$(/bin/date)] PL1=20W MSR operation successful (hardware power must still be checked)."
