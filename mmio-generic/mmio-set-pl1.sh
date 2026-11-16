#!/bin/bash
# 便携读-改-写脚本：把 MMIO RAPL 的 PL1 设为指定瓦特，保留 PL2/锁位/窗口/enable 位。
# 基于通用 voltageshift mmio-read / mmio-write，不写死任何瓦特。
#
# 用法:  sudo ./mmio-set-pl1.sh <PL1瓦特> [PL2瓦特]
#   例:  sudo ./mmio-set-pl1.sh 20
#        sudo ./mmio-set-pl1.sh 20 61
#
# 依赖: 同目录或 PATH 中的 voltageshift（通用 MMIO 版）、python3、root。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VS=""
if [ -x "$SCRIPT_DIR/voltageshift" ]; then
  VS="$SCRIPT_DIR/voltageshift"
elif command -v voltageshift >/dev/null 2>&1; then
  VS="$(command -v voltageshift)"
else
  echo "ERROR: 找不到 voltageshift CLI（放在脚本同目录或加入 PATH）"; exit 1
fi

[ "$(id -u)" -eq 0 ] || { echo "ERROR: 请用 sudo 以 root 运行"; exit 1; }
[ $# -ge 1 ] || { echo "用法: sudo $0 <PL1瓦特> [PL2瓦特]"; exit 1; }

PL1_W="$1"; PL2_W="${2:-}"
case "$PL1_W" in (*[!0-9.]*|'') echo "ERROR: PL1 必须是数字"; exit 1;; esac
if [ -n "$PL2_W" ]; then
  case "$PL2_W" in (*[!0-9.]*|'') echo "ERROR: PL2 必须是数字"; exit 1;; esac
fi
command -v python3 >/dev/null 2>&1 || { echo "ERROR: 需要 python3"; exit 1; }

RAPL_OFF=59a0
UNIT_OFF=5938

# 1) 读功率单位指数（MMIO 0x5938 解码行: power=1/2^N W）
unit_out="$("$VS" mmio-read "$UNIT_OFF" 2>&1)" || { echo "ERROR: 读 $UNIT_OFF 失败"; echo "$unit_out"; exit 1; }
EXP="$(printf '%s\n' "$unit_out" | sed -n 's/.*power=1\/2^\([0-9][0-9]*\) W.*/\1/p' | head -1)"
[ -n "$EXP" ] || { echo "ERROR: 无法解析功率单位指数"; echo "$unit_out"; exit 1; }
echo "功率单位: 1/2^$EXP W"

# 2) 读当前 64 位 RAPL 限制
rapl_out="$("$VS" mmio-read "$RAPL_OFF" 64 2>&1)" || { echo "ERROR: 读 $RAPL_OFF 失败"; echo "$rapl_out"; exit 1; }
CUR="$(printf '%s\n' "$rapl_out" | sed -n 's/.*\[0x59a0\] = 0x\([0-9a-fA-F]\{16\}\).*/\1/p' | head -1)"
[ -n "$CUR" ] || { echo "ERROR: 无法解析 RAPL 值"; echo "$rapl_out"; exit 1; }
echo "当前 RAPL: 0x$CUR"
printf '%s\n' "$rapl_out" | grep 'PL1=' || true

# 3) 计算新值（python3 任意精度，避免 64 位浮点丢位）
NEW="$(python3 - "$CUR" "$EXP" "$PL1_W" "$PL2_W" <<'PY'
import sys
cur=int(sys.argv[1],16); exp=int(sys.argv[2]); pl1=float(sys.argv[3]); pl2=sys.argv[4]
if (cur>>63)&1:
    print("LOCKED"); sys.exit(0)
unit=1<<exp
lo=cur&0xffffffff; hi=(cur>>32)&0xffffffff
p1=int(round(pl1*unit))
if p1<0 or p1>0x7fff:
    print("RANGE"); sys.exit(0)
new_lo=(lo&~0x7fff)|p1
new_hi=hi
if pl2:
    p2=int(round(float(pl2)*unit))
    if p2<0 or p2>0x7fff:
        print("RANGE2"); sys.exit(0)
    new_hi=(hi&~0x7fff)|p2
print("%016x"%((new_hi<<32)|new_lo))
PY
)"
case "$NEW" in
  LOCKED) echo "拒绝: RAPL 锁位(bit63)已置位，不写入"; exit 1;;
  RANGE)  echo "ERROR: PL1 原始值超出 15 位范围"; exit 1;;
  RANGE2) echo "ERROR: PL2 原始值超出 15 位范围"; exit 1;;
esac
echo "目标 RAPL: 0x$NEW  (PL1=${PL1_W}W${PL2_W:+, PL2=${PL2_W}W})"

# 4) 写入并回读校验
write_out="$("$VS" mmio-write "$RAPL_OFF" "$NEW" 64 2>&1)" || { echo "ERROR: 写入失败"; echo "$write_out"; exit 1; }
echo "$write_out"
if printf '%s\n' "$write_out" | grep -q 'MISMATCH'; then
  echo "结果: 回读不一致（被锁或固件覆盖）"; exit 1
fi

# 5) 最终解码确认
echo "--- 写入后 ---"
"$VS" mmio-read "$RAPL_OFF" 64
echo "结果: OK"