# P0：WindowServer 分析

完整结论见 [windowserver-root-cause.md](windowserver-root-cause.md)。提供的 watchdog
文字仅能证明 WindowServer 停止 check-in；不能证明 WhateverXe、GPU、CPU 电源管理或
睡眠唤醒就是根因。修改图形配置前，先保存并收集原始 IPS、spin 和诊断文件。
