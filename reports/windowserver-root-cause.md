# WindowServer watchdog 评估

状态：**未定因。任务书引用的 `.panic`、`.ips`、`.spin`、睡眠唤醒和关机报告均未提供。**

给出的片段（`watchdogd`、“no successful checkins from WindowServer”、120 秒内两次
induced crash）只证明最终 watchdog 条件：WindowServer 未继续 check-in。它不能指出
阻塞组件；这与已证实的 VoltageShift General Protection Fault 是不同类别的故障。

## 假设，不是结论

| 假设 | 当前证据 | 仍需证据 |
| --- | --- | --- |
| Intel 显示管线 / WhateverXe 兼容性 | 无 | WindowServer `.ips`、watchdog `.spin`、已加载 WhateverXe 版本、同次内核回溯的 GPU/IGPU 栈 |
| 睡眠唤醒后的显示重初始化失败 | 无 | 与 `pmset -g log`、Sleep Wake Failure 和显示唤醒事件的时间关联 |
| CPU/电源管理导致调度饥饿 | 无 | 与功耗守护日志、可响应内核或受阻 WindowServer 栈的关联 |
| 一般系统或应用卡死 | 无 | 完整 WindowServer 线程栈及对应时间窗的统一日志 |

目前没有证据支持禁用 GPU 加速或移除 `-wex-tgl-blfull`；也不要移除
`-vi2c-force-polling`。应先用只读采集脚本取得报告，再把其时间戳与电源/睡眠事件比对。

## 低风险的下一批证据

1. 下次故障后运行 `tools/collect-readonly-diagnostics.sh`。
2. 原样保存 `WindowServer*.ips`、watchdog spin、睡眠唤醒诊断和 shutdown stall。
3. 记录已安装/加载的 WhateverXe 版本、OpenCore 版本及显示连接器配置；不要为收集
   证据而改动它们。
4. 将来如获准进行受控实验，每次启动只改变一项，并保留可启动的 USB EFI；本仓库
   不改动这些启动参数。
