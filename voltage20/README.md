# MateBook X Pro 2021 — One-reboot PL1 20W test

适用：macOS 15.8.1 / OpenCore / Intel Core i7-1165G7。**实验版**，仅供测试。Windows 已通过 ThrottleStop 验证过 20W 并不保证 macOS 上同样稳定。

## 功能
- 源码固定为 VoltageShiftSecure upstream commit 6b4612c004a4631c4c3e4831f2a6989718dea6a5。
- 将独立的 'pl1-20w' 命令注入 CLI，安全地从 MSR 0x606 读取 RAPL 单位、从 0x610 读取原始限制，只修改 PL1 原始值字段（bit 0–14），保留启用位、时间窗、PL2、锁位、Turbo 和电压。
- MSR 0x610 已锁定、PL1 未启用、MSR 读取失败时，不写入。
- 自动回读验证。但仅能证明 MSR 值改变，**不保证 MMIO/EC 的 10 W 上限解除**。
- macOS 登录后系统级 launchd 默认仅在 **AC 电源供电** 时尝试，启动和每 300 秒检查一次（处理固件重新设置功率限制）。电池供电下不提高功率。
- 完整保留现有 WhateverXe PWM 和 Goodix I2C 配置。无需修改原有 boot-args。

## 安装（只需一次重启）
1. 将整个实验包解压至 macOS 文件夹。
2. 在 OpenCore 当前启动的 EFI 上操作。挂载方法：终端运行 'diskutil list'，找到正确的 EFI 分区，然后 'sudo diskutil mount diskXs1'（不要照抄 diskXs1）。
3. 确保能够从另外的 U 盘启动原来正常的 EFI。不可在无回退方案的情况下测试内核扩展。
4. 进入解压后的文件夹，运行 'bash install-20w.sh'。脚本备份当前 config.plist，只添加 VoltageShift.kext，不动背光、触摸板或其他驱动。安装 LaunchDaemon 实现重启后自动尝试 20 W。
5. **重启一次**。运行以下两条命令检查：
   - 'sudo tail -40 /var/log/matebook-pl1-20.log'
   - 'sudo powermetrics --samplers cpu_power -i 1000 -n 5'
6. 为确认真实功耗是否超过 10 W，可以在同一次启动中运行 CPU 负载测试，无需再重启。若依然 10W，说明可能有 MMIO/EC/其他限制，不能通过加大 MSR 值硬突破。

## 回退
在解压目录运行 'bash uninstall-20w.sh'，脚本删除本实验添加的 Kext、launchd、二进制与 OpenCore 条目；重启后恢复原先固件功率策略。若发生启动黑屏/卡死，改用保留的原版 EFI 启动并从备用环境移除本次新增 Kext。

## 安全限制
- **不做降压、不更改 Turbo 和 PL2、不写 BIOS 或 MMIO、不关闭温度保护。**
- PL1=20W 不意味着 CPU 永久消耗 20 W，仅提升持续功率上限。
- 这不是厂商支持的工具，内核扩展可能无法兼容 Sequoia 15.8.1；安装前必须备份 EFI。
- 当前版本不包含绕过锁位功能，写入失败将打印错误并保留限制。
- 高频后台负载、CPU 高温、频率不稳、风扇异常或睡眠唤醒异常时请立即回退。
