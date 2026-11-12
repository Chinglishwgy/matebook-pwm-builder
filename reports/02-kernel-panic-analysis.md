# P0：内核 Panic 分析

完整结论见 [kernel-panic-root-cause.md](kernel-panic-root-cause.md)。任务书提供证据
的只有 19:25:12 那份 General Protection Fault：VoltageShift 执行了
`RDMSR 0x776`。另两份指定的 Panic 原始文件尚未提供，必须先读取，不能直接归为同因。
