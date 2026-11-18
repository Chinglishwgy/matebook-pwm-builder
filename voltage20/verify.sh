#!/bin/bash
# Default mode is filesystem/launchd verification. --hardware performs the
# explicitly approved, allow-listed MMIO read, never a generic MSR read.
set -euo pipefail
BIN=/usr/local/libexec/matebook-pl1/voltageshift
DAEMON=/Library/LaunchDaemons/com.matebook.mmio-20.plist

test -x "$BIN" || { echo "VERIFY_ERROR: missing $BIN"; exit 2; }
test -f "$DAEMON" || { echo "VERIFY_ERROR: missing $DAEMON"; exit 3; }
/usr/bin/plutil -lint "$DAEMON"
/usr/sbin/kmutil showloaded | /usr/bin/grep -qi 'com\.sicreative\.VoltageShift' || {
  echo "VERIFY_ERROR: VoltageShift Kext is not loaded"; exit 4;
}
/bin/launchctl print-disabled system | /usr/bin/grep -E 'com\.matebook\.(pl1-20|mmio-20)' || true
echo "VERIFY_OK: files are present and the Kext is loaded. No register access performed."

if [ "${1:-}" = --hardware ]; then
  echo "VERIFY_HARDWARE: calling only the fixed MMIO read endpoint."
  exec "$BIN" mmio-read
fi
