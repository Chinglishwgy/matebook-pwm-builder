#!/bin/bash
# 用 sudo 运行：把启动盘 EFI 里的 VoltageShift.kext 替换为通用 MMIO 版。
# 先备份旧驱动、校验 config.plist 引用，确认后才替换；路径异常即中止。
#
#   sudo bash install-mmio-generic.sh [EFI分区，默认 disk0s1]
#
# 脚本须与新的 VoltageShift.kext 放在同一目录。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEW_KEXT="$SCRIPT_DIR/VoltageShift.kext"
EFI_DEV="${1:-disk0s1}"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: 请用 sudo 运行"; exit 1; }
[ -d "$NEW_KEXT" ] || { echo "ERROR: 同目录找不到 VoltageShift.kext: $NEW_KEXT"; exit 1; }

echo "== 新驱动 =="
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$NEW_KEXT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$NEW_KEXT/Contents/Info.plist"

echo "== 挂载 EFI: $EFI_DEV =="
diskutil mount "$EFI_DEV" >/dev/null 2>&1 || diskutil mount "$EFI_DEV"
MP="$(diskutil info "$EFI_DEV" | awk -F': *' '/Mount Point/{print $2; exit}')"
[ -n "$MP" ] && [ -d "$MP" ] || { echo "ERROR: 无法取得挂载点"; exit 1; }
echo "挂载点: $MP"

OC="$MP/EFI/OC"
[ -d "$OC/Kexts" ] || { echo "ERROR: $OC/Kexts 不存在，EFI 布局不符，中止"; exit 1; }
[ -f "$OC/config.plist" ] || { echo "ERROR: 找不到 config.plist，中止"; exit 1; }
TARGET="$OC/Kexts/VoltageShift.kext"

echo "== config.plist 中的 VoltageShift 引用 =="
if grep -q 'VoltageShift.kext' "$OC/config.plist"; then
  grep -n 'VoltageShift.kext' "$OC/config.plist" | head
else
  echo "WARNING: config.plist 未引用 VoltageShift.kext——替换后可能不会被注入！"
  echo "         请确认 Kernel->Add 里有该项；仍要继续吗？"
fi

echo "== 当前 EFI 里的旧驱动 =="
if [ -d "$TARGET" ]; then
  /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist" 2>/dev/null || echo "(无法读版本)"
else
  echo "(EFI 中尚无 VoltageShift.kext，将新增)"
fi

echo
echo "计划: 备份旧驱动 -> 用通用 MMIO 版替换 $TARGET"
printf "确认执行？[y/N] "
read -r ans
case "$ans" in y|Y|yes|YES) ;; *) echo "已取消"; exit 0;; esac

TS="$(date +%Y%m%d-%H%M%S)"
if [ -d "$TARGET" ]; then
  BACKUP="$MP/EFI/VoltageShift-backup-$TS.kext"
  echo "备份旧驱动 -> $BACKUP"
  ditto "$TARGET" "$BACKUP"
  rm -rf "$TARGET"
fi
echo "写入新驱动 ..."
ditto "$NEW_KEXT" "$TARGET"
sync

echo "== 替换后校验 =="
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$TARGET/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :OSBundleLibraries:com.apple.iokit.IOPCIFamily' "$TARGET/Contents/Info.plist"
echo
echo "完成。请重启以加载新驱动；重启后用同目录 voltageshift 测试："
echo "  sudo ./voltageshift mmio-read 5938"
echo "  sudo ./voltageshift mmio-read 59a0 64"
echo "  sudo ./mmio-set-pl1.sh 20"
echo "回滚: 把 $MP/EFI/VoltageShift-backup-$TS.kext 复制回 $TARGET 再重启。"