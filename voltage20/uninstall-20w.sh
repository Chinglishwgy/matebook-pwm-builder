#!/bin/bash
# Remove only the additions made by install-20w.sh. Does not touch PWM/I2C.
set -euo pipefail
EFI_MOUNT="${EFI_MOUNT:-/Volumes/EFI}"
CFG="$EFI_MOUNT/EFI/OC/config.plist"
DAEMON="/Library/LaunchDaemons/com.matebook.pl1-20.plist"
[ -f "$CFG" ] || { echo "Cannot find boot EFI config: $CFG"; exit 1; }
sudo -v
stamp="$(date +%Y%m%d-%H%M%S)"
sudo cp -p "$CFG" "$CFG.before-voltage20-uninstall-$stamp"

if [ -f "$DAEMON" ]; then
  sudo launchctl bootout system "$DAEMON" >/dev/null 2>&1 || true
  sudo rm -f "$DAEMON"
fi
sudo rm -f /usr/local/libexec/matebook-pl1/auto-20w.sh
sudo rm -f /usr/local/libexec/matebook-pl1/voltageshift
sudo rmdir /usr/local/libexec/matebook-pl1 2>/dev/null || true

sudo /usr/bin/python3 - "$CFG" <<'PY'
import plistlib,sys
p=sys.argv[1]
with open(p,"rb") as f: obj=plistlib.load(f)
items=obj["Kernel"]["Add"]
obj["Kernel"]["Add"]=[i for i in items if i.get("BundlePath")!="VoltageShift.kext"]
with open(p,"wb") as f: plistlib.dump(obj,f,fmt=plistlib.FMT_XML,sort_keys=False)
print("OpenCore VoltageShift entry removed")
PY
sudo rm -rf "$EFI_MOUNT/EFI/OC/Kexts/VoltageShift.kext"
/usr/bin/plutil -lint "$CFG"
echo "Rollback staged; reboot to restore firmware/default PL1 policy."
echo "Other EFI settings, including WhateverXe PWM and Goodix I2C, remain untouched."
