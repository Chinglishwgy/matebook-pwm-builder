# P0：环境盘点

当前工作区是源码检出，并非故障 MateBook 系统；这里没有本机 EFI、已加载 Kext、
launchd 状态或 `DiagnosticReports`。下表仅转录任务书中的信息，**并非实机探测结果**。

| 项目 | 已提供状态 | 验证状态 |
| --- | --- | --- |
| CPU | Core i7-1165G7 / Tiger Lake-U | 未实机验证 |
| macOS | Sequoia 15.8.1 (24H32) | 未实机验证 |
| SMBIOS | MacBookPro16,2 | 未实机验证 |
| 引导器 | OpenCore；EFI 可能在 USB | 实际生效 EFI 未知 |
| Kext | VoltageShiftSecure、WhateverXe、VoodooI2C/Goodix | 已加载版本未知 |
| LaunchDaemon | 两个 20W 项已 disable/bootout | 未实机验证 |
| 压力进程 | 无残留 `yes` | 未实机验证 |

请在故障电脑运行 `tools/collect-readonly-diagnostics.sh` 收集缺失证据。它不改动系统，
也不发起 MSR 请求。安装前必须挂载并显式设置已确认的实际 OpenCore EFI：`EFI_MOUNT`；
工具和本文档绝不假设 `/Volumes/EFI` 就是生效 EFI。
