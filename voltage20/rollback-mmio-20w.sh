#!/bin/bash
# Roll back ONLY MMIO experiment; restore original VoltageShift Kext and CLI.
set -euo pipefail
EFI_MOUNT="${EFI_MOUNT:-/Volumes/EFI}"
KEXT="$EFI_MOUNT/EFI/OC/Kexts/VoltageShift.kext"
EXEC="/usr/local/libexec/matebook-pl1/voltageshift"
DAEMON="/Library/LaunchDaemons/com.matebook.mmio-20.plist"
BACKUP="${1:-}"
[ -n "$BACKUP" ] || { echo "Usage: bash rollback-mmio-20w.sh ~/Desktop/MateBook-MMIO-Backup-YYYYmmdd-HHMMSS"; exit 1; }
[ -d "$BACKUP/VoltageShift.kext" ] || { echo "Backup Kext not found"; exit 1; }
[ -f "$BACKUP/voltageshift" ] || { echo "Backup CLI not found"; exit 1; }
[ -d "$KEXT" ] || { echo "Active EFI not mounted? $KEXT"; exit 1; }
sudo -v
if [ -f "$DAEMON" ]; then
  sudo launchctl bootout system "$DAEMON" 2>/dev/null || true
  sudo rm -f "$DAEMON"
fi
sudo rm -f /usr/local/libexec/matebook-pl1/auto-mmio20.sh
STAGE="$EFI_MOUNT/EFI/OC/Kexts/VoltageShift-rollback-stage"
sudo rm -rf "$STAGE"
sudo ditto "$BACKUP/VoltageShift.kext" "$STAGE"
sudo test -s "$STAGE/Contents/MacOS/VoltageShift"
sudo rm -rf "$KEXT"
sudo mv "$STAGE" "$KEXT"
sudo install -o root -g wheel -m 0755 "$BACKUP/voltageshift" "$EXEC"
echo "MMIO modification rollback staged. Restart once to load the old Kext."
echo "Existing MSR 20W launchd, PWM backlight and Goodix drivers are unchanged."
