#!/bin/bash
# Conservative MMIO PL1 boost, only when on AC. Requires Kext and CLI extensions.
set -euo pipefail
BIN="/usr/local/libexec/matebook-pl1/voltageshift"
echo "[$(/bin/date)] MMIO20: AC-only check"
if [ "$(/usr/sbin/sysctl -n machdep.cpu.brand_string)" != "11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz" ]; then
  echo "MMIO20_SKIPPED: processor identity mismatch"
  exit 10
fi
if ! /usr/bin/pmset -g batt | /usr/bin/grep -q "AC Power"; then
  echo "MMIO20_SKIPPED: battery power (do not raise PL1)"
  exit 0
fi
if [ ! -x "$BIN" ]; then echo "MMIO20_ERROR: missing CLI"; exit 11; fi

for i in $(/usr/bin/seq 1 20); do
  if /usr/bin/kmutil showloaded 2>/dev/null | /usr/bin/grep -q 'com.sicreative.VoltageShift'; then
    break
  fi
  /bin/sleep 2
done

# User-facing diagnostic before trying any write; one process does not force MSR/EC.
echo "MMIO20: pre-write snapshot"
/usr/local/libexec/matebook-pl1/voltageshift mmio-read || {
  echo "MMIO20_ERROR: read-only MMIO verification failed; will not write"
  exit 12
}
echo "MMIO20: guarded 20W write (only if MMIO PL1 5-20W, enabled and unlocked)"
/usr/local/libexec/matebook-pl1/voltageshift mmio20 || {
  echo "MMIO20_ERROR: change rejected or unsupported; no force or lock changes"
  exit 13
}
echo "[$(/bin/date)] MMIO20 done; actual CPU package power not yet measured"
