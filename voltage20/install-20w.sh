#!/bin/bash
# One-time installation: OpenCore Kext + 20W launchd helper; only one reboot required.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
EFI_MOUNT="${EFI_MOUNT:-/Volumes/EFI}"
CFG="$EFI_MOUNT/EFI/OC/config.plist"
KEXT_DIR="$EFI_MOUNT/EFI/OC/Kexts"
LIBEXEC="/usr/local/libexec/matebook-pl1"
DAEMON="/Library/LaunchDaemons/com.matebook.pl1-20.plist"

[ "$(uname -m)" = "x86_64" ] || { echo "Only Intel macOS is supported."; exit 1; }
[ -d "$ROOT/VoltageShift.kext" ] || { echo "Missing compiled VoltageShift.kext in package"; exit 1; }
[ -x "$ROOT/voltageshift" ] || { echo "Missing compiled voltageshift CLI"; exit 1; }
[ -f "$CFG" ] || {
  echo "Cannot find $CFG. Mount the EFI actually used for boot first."
  echo "Use 'diskutil list' and 'sudo diskutil mount diskXs1'."
  echo "Or run: EFI_MOUNT=/Volumes/YourEFI bash install-20w.sh"
  exit 1
}
[ -d "$KEXT_DIR" ] || { echo "No OpenCore Kexts directory at $KEXT_DIR"; exit 1; }
echo "EFI target: $CFG"
echo "Do not run this against a different, unused EFI partition."
sudo -v
stamp="$(date +%Y%m%d-%H%M%S)"
sudo cp -p "$CFG" "$CFG.before-voltage20-$stamp"
echo "Config backup: $CFG.before-voltage20-$stamp"

sudo rm -rf "$KEXT_DIR/VoltageShift.kext"
sudo ditto "$ROOT/VoltageShift.kext" "$KEXT_DIR/VoltageShift.kext"

# Edit only the VoltageShift Kext row. Preserve framebuffer, PWM and I2C entries.
sudo /usr/bin/python3 - "$CFG" <<'PY'
import plistlib, sys
from pathlib import Path
p=Path(sys.argv[1])
with p.open("rb") as f: obj=plistlib.load(f)
items=obj["Kernel"]["Add"]
matches=[i for i in items if i.get("BundlePath")=="VoltageShift.kext"]
if len(matches)>1: raise SystemExit("Duplicate VoltageShift entries found; aborting")
data=dict(Arch="x86_64",BundlePath="VoltageShift.kext",
          Comment="MateBook PL1 20W: VoltageShiftSecure EFI helper",
          Enabled=True,ExecutablePath="Contents/MacOS/VoltageShift",
          MaxKernel="",MinKernel="",PlistPath="Contents/Info.plist")
if matches: matches[0].update(data)
else: items.append(data)
with p.open("wb") as f: plistlib.dump(obj,f,fmt=plistlib.FMT_XML,sort_keys=False)
print("Kext entry ready in OpenCore config")
PY
/usr/bin/plutil -lint "$CFG"

sudo mkdir -p "$LIBEXEC"
sudo install -o root -g wheel -m 0755 "$ROOT/voltageshift" "$LIBEXEC/voltageshift"
sudo install -o root -g wheel -m 0755 "$ROOT/auto-20w.sh" "$LIBEXEC/auto-20w.sh"
sudo install -o root -g wheel -m 0644 "$ROOT/com.matebook.pl1-20.plist" "$DAEMON"
/usr/bin/plutil -lint "$DAEMON"
echo ""
echo "Setup complete. One reboot is needed to load the new Kext."
echo "After reboot PL1=20W will be attempted automatically; PL2 is preserved."
echo "If MSR locked or Kext unavailable, helper fails without force-writing."
echo "After reboot: sudo tail -40 /var/log/matebook-pl1-20.log"
echo "Measure: sudo powermetrics --samplers cpu_power -i 1000 -n 5"
echo "For rollback: sudo bash uninstall-20w.sh"
