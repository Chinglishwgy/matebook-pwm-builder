#!/bin/bash
# Collect diagnostic evidence only.  This script does not write MSRs, MMIO,
# NVRAM, the EFI, or launchd state; in particular it never reads MSR 0x776.
set -euo pipefail

OUT="${1:-$PWD/matebook-readonly-diagnostics-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
run() { "$@" >"$OUT/$1.txt" 2>&1 || true; }

run /usr/bin/sw_vers
run /usr/sbin/sysctl machdep.cpu.brand_string machdep.cpu.family machdep.cpu.model
run /usr/sbin/kmutil showloaded
run /usr/bin/pmset -g custom
run /usr/bin/pmset -g batt
run /usr/bin/pmset -g log
run /usr/sbin/ioreg -l -p IOService
run /usr/sbin/diskutil list
run /usr/sbin/diskutil info -all
run /usr/sbin/nvram -p

/bin/launchctl print-disabled system >"$OUT/launchd-disabled-system.txt" 2>&1 || true
/bin/launchctl print system/com.matebook.pl1-20 >"$OUT/launchd-pl1-20.txt" 2>&1 || true
/bin/launchctl print system/com.matebook.mmio-20 >"$OUT/launchd-mmio-20.txt" 2>&1 || true
/usr/bin/mdfind 'kMDItemFSName == "VoltageShift.kext"' >"$OUT/voltageshift-kext-locations.txt" 2>&1 || true

REPORTS=/Library/Logs/DiagnosticReports
if [ -d "$REPORTS" ]; then
  /usr/bin/find "$REPORTS" -maxdepth 1 -type f \( -name 'Kernel-*.panic' -o -name 'WindowServer*.ips' -o -name '*userspace_watchdog_timeout.spin' -o -name 'Sleep Wake Failure*.diag' -o -name '*shutdownStall*' \) -print \
    >"$OUT/relevant-report-paths.txt"
  while IFS= read -r report; do
    /usr/bin/cp -p "$report" "$OUT/" || true
  done <"$OUT/relevant-report-paths.txt"
fi

cat >"$OUT/README.txt" <<'EOF'
Collection complete. Share this directory without changing the system.
No MSR command was issued, and MSR 0x776 was not read.
EOF
echo "Collected read-only diagnostics in: $OUT"
