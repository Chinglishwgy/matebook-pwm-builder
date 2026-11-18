#!/bin/bash
# Roll back ONLY MMIO experiment; restore original VoltageShift Kext and CLI.
set -euo pipefail
: "${EFI_MOUNT:?Set EFI_MOUNT to the already-mounted, confirmed active OpenCore EFI.}"
case "$EFI_MOUNT" in /*) ;; *) echo "EFI_MOUNT must be an absolute path"; exit 64;; esac
KEXT="$EFI_MOUNT/EFI/OC/Kexts/VoltageShift.kext"
EXEC="/usr/local/libexec/matebook-pl1/voltageshift"
DAEMON="/Library/LaunchDaemons/com.matebook.mmio-20.plist"
BACKUP="${1:-}"
[ -n "$BACKUP" ] || { echo "Usage: bash rollback-mmio-20w.sh ~/Desktop/MateBook-MMIO-Backup-YYYYmmdd-HHMMSS"; exit 1; }
[ -d "$BACKUP/VoltageShift.kext.original" ] || { echo "Backup Kext not found"; exit 1; }
[ -f "$BACKUP/voltageshift" ] || { echo "Backup CLI not found"; exit 1; }
[ -d "$KEXT" ] || { echo "Active EFI not mounted? $KEXT"; exit 1; }
sudo -v
if [ -f "$DAEMON" ]; then
  sudo launchctl bootout system "$DAEMON" 2>/dev/null || true
  sudo rm -f "$DAEMON"
fi
sudo rm -f /usr/local/libexec/matebook-pl1/auto-mmio20.sh
STAGE_ROOT="$(/usr/bin/mktemp -d "$EFI_MOUNT/EFI/OC/Kexts/.VoltageShift-rollback-stage.XXXXXX")"
STAGE="$STAGE_ROOT/VoltageShift.kext"
sudo ditto "$BACKUP/VoltageShift.kext.original" "$STAGE"
sudo test -s "$STAGE/Contents/MacOS/VoltageShift"
sudo mv "$KEXT" "$BACKUP/VoltageShift.kext.failed-build"
sudo mv "$STAGE" "$KEXT"
sudo rmdir "$STAGE_ROOT"
sudo install -o root -g wheel -m 0755 "$BACKUP/voltageshift" "$EXEC"
echo "MMIO modification rollback staged. Restart once to load the old Kext."
echo "Existing MSR 20W launchd, PWM backlight and Goodix drivers are unchanged."
