#!/bin/bash
# One-reboot upgrade from the existing, already working VoltageShiftSecure EFI install.
# Replaces VoltageShift.kext and CLI; keeps current MSR 20W job and all other EFI parts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
EFI_MOUNT="${EFI_MOUNT:-/Volumes/EFI}"
CFG="$EFI_MOUNT/EFI/OC/config.plist"
KEXT="$EFI_MOUNT/EFI/OC/Kexts/VoltageShift.kext"
EXEC="/usr/local/libexec/matebook-pl1/voltageshift"
DAEMON="/Library/LaunchDaemons/com.matebook.mmio-20.plist"
HOME_DESKTOP="$HOME/Desktop"

[ "$(uname -m)" = "x86_64" ] || { echo "ERROR: Intel Mac only"; exit 1; }
[ -d "$ROOT/VoltageShift.kext" ] || { echo "ERROR: Missing packaged Kext"; exit 1; }
[ -x "$ROOT/voltageshift" ] || { echo "ERROR: Missing packaged CLI"; exit 1; }
[ -f "$CFG" ] || { echo "ERROR: Mount your ACTIVE EFI before installation: $CFG"; exit 1; }
[ -d "$KEXT" ] || { echo "ERROR: Existing VoltageShift Kext not found in EFI"; exit 1; }
[ -x "$EXEC" ] || { echo "ERROR: Previous VoltageShiftSecure CLI not found"; exit 1; }
/usr/bin/python3 - "$CFG" <<'PY'
import plistlib,sys
with open(sys.argv[1],"rb") as f: obj=plistlib.load(f)
p=[x for x in obj.get("Kernel",{}).get("Add",[]) if x.get("BundlePath")=="VoltageShift.kext"]
assert len(p)==1 and p[0].get("Enabled") is True, "VoltageShift Kext entry must be enabled in ACTIVE EFI"
assert p[0].get("ExecutablePath")=="Contents/MacOS/VoltageShift", "Unexpected existing VoltageShift executable path"
print("OpenCore VoltageShift entry is enabled; no config change needed")
PY

echo "Target EFI: $CFG"
echo "Save a fallback bootable USB EFI before proceeding."
sudo -v
BACKUP="$HOME_DESKTOP/MateBook-MMIO-Backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
sudo ditto "$KEXT" "$BACKUP/VoltageShift.kext"
sudo cp -p "$EXEC" "$BACKUP/voltageshift"
cp "$CFG" "$BACKUP/config.plist"
if [ -f "$DAEMON" ]; then sudo cp -p "$DAEMON" "$BACKUP/com.matebook.mmio-20.plist"; fi
echo "Backup: $BACKUP"

# Stage completely before replacing EFI Kext.
STAGED="$EFI_MOUNT/EFI/OC/Kexts/VoltageShift-stage"
sudo rm -rf "$STAGED"
sudo ditto "$ROOT/VoltageShift.kext" "$STAGED"
sudo test -s "$STAGED/Contents/MacOS/VoltageShift" || { echo "ERROR: staged Kext binary missing"; exit 1; }
sudo rm -rf "$KEXT"
sudo mv "$STAGED" "$KEXT"
sudo install -o root -g wheel -m 0755 "$ROOT/voltageshift" "$EXEC"
sudo install -o root -g wheel -m 0755 "$ROOT/auto-mmio20.sh" /usr/local/libexec/matebook-pl1/auto-mmio20.sh
sudo install -o root -g wheel -m 0644 "$ROOT/com.matebook.mmio-20.plist" "$DAEMON"
/usr/bin/plutil -lint "$DAEMON"
echo
echo "Installation staged; restart once to load the extended VoltageShift Kext."
echo "The existing MSR PL1 daemon remains installed and will continue targeting 20W."
echo "MMIO auto attempt (AC-only) activates after reboot."
echo "After reboot: sudo tail -80 /var/log/matebook-mmio-20.log"
echo "If boot issues occur, boot from your known-working USB EFI and restore the backup."
