# 通用 MCHBAR MMIO 读写（VoltageShiftSecure 扩展）

在**保留原版全部功能**的前提下，为 VoltageShift 增加类似原版 MSR `read`/`write` 的
**通用 MMIO 读取/写入**能力。不再像旧定制版那样把 MMIO 写死成「只读 0x59a0 / 只写 20W」，
偏移、数值、位宽全部可传参。

- 目标机：MateBook X Pro 2021（Intel i7-1165G7，Tiger Lake）
- 目标系统：**macOS 26.7.2 (Tahoe)**，x86_64
- 构建：GitHub Actions `macos-15-intel` runner，macOS 15 SDK（与现役 1.27 kext 相同，
  已验证可在 26.7.2 加载），上游固定提交 `xCuri0/VoltageShiftSecure@6b4612c`

## 新命令

偏移均相对 **PCI 00:00.0 的 MCHBAR 基址**（十六进制，不带 0x 前缀）。位宽可选 `32`/`64`，默认 `32`。

```
sudo voltageshift mmio-read  <HEX_OFFSET> [32|64]
sudo voltageshift mmio-write <HEX_OFFSET> <HEX_VALUE> [32|64]
```

Tiger Lake 常用寄存器：
- `0x5938` RAPL 功率单位（32 位）
- `0x59a0` 封装 RAPL 功耗限制 PL1/PL2（64 位：低 32=PL1，高 32=PL2）

### 示例

```
# 读功率单位（自动解码 1/2^n W、J、s）
sudo voltageshift mmio-read 5938

# 读 PL1/PL2（64 位，自动按 MSR 0x606 单位换算成瓦特并显示 enable/lock）
sudo voltageshift mmio-read 59a0 64

# 读任意 MCHBAR 寄存器（32 位）
sudo voltageshift mmio-read 59a4

# 写整个 64 位 RAPL 限制寄存器（自行构造完整值）
sudo voltageshift mmio-write 59a0 004281e800dd80a8 64
```

### 只改 PL1 到指定瓦特、保留其余位（读-改-写）

以 20W 为例（功率单位指数取自 `mmio-read 5938`，本机为 3，即 1/8 W）：

1. `sudo voltageshift mmio-read 59a0 64` 记下当前值，低 32 位记为 `LO`、高 32 位记为 `HI`。
2. 计算新低位：`newLO = (LO & ~0x7fff) | (20 << 3)`，即清掉 bit0–14 后填入 `20*8=160=0xA0`。
3. 拼回 64 位：`value = (HI << 32) | newLO`，高位 `HI`（PL2/锁位/窗口）原样保留。
4. `sudo voltageshift mmio-write 59a0 <value> 64`，工具自动回读校验。

> 也可以继续用原版 `sudo voltageshift power <PL1> <PL2>` 走 MSR 0x610 设置功耗墙；
> MMIO 与 MSR 是两套寄存器，按需在对应一侧操作。

## 安全边界

- **仅 root** 可调用（沿用 VoltageShiftSecure 的 newUserClient 管理员校验）。
- 访问被限制在 **MCHBAR 起始 32KB 窗口**内，要求自然对齐（32 位 4 字节、64 位 8 字节），
  越界/未对齐直接拒绝。Tiger Lake MCHBAR 至少 32KB（RAPL 位于 0x59xx），窗口不会越过 BAR。
-  uncached（`kIOMapInhibitCache`）映射；写后**自动回读**并报告 `OK` 或 `MISMATCH`。
- **不屏蔽、不强改锁位**：寄存器若被锁，写入会回读不一致并提示 `MISMATCH`，而不是硬改。
- 仅 Intel family 6；MCHBAR 未启用或基址高于 4GB 时拒绝。

⚠️ 通用写能力意味着你可以写 MCHBAR 内任意寄存器——写错关键寄存器可能死机/重启。
请先读后写、明确每一位含义再操作。

## 与旧定制版的区别

| | 旧 `mmio20` | 本通用版 |
|---|---|---|
| 偏移 | 固定 0x59a0 | 任意（窗口内） |
| 写入值 | 固定抬到 20W | 任意值 |
| 位宽 | 仅低 32 的 PL1 字段 | 32 / 64 全寄存器 |
| 读 | 仅 0x59a0 | 任意偏移 |

## 原版功能保持不变

`offset` / `turbo` / `power` / `read` / `write` / `info` / `mon` / `buildlaunchd` /
`removelaunchd` 等全部照旧。本补丁**不**注入任何固定 20W 逻辑。

## 安装与注意

1. 用包内 `VoltageShift.kext` 替换 EFI 中的同名 kext，重启；CLI 用包内 `voltageshift`。
2. **不要与原版 VoltageShift 驱动或其他 MMIO 工具混用**——此前混用曾导致 Kernel Panic。
   同一时间只加载一套驱动。
3. 本包未签名（`CODE_SIGNING_ALLOWED=NO`），依赖你 EFI 里现有的 AMFIPass / OpenCore
   kext 注入方式加载，与现役 1.27 一致。