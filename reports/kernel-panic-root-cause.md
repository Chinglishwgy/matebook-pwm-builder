# VoltageShift 内核 Panic 根因报告

状态：**已确认 `Kernel-2026-11-11-192512.panic` 的根因；工作区没有其余 Panic
原始文件，不能认定它们同因。**

## 已确认的调用路径

任务书给出的 Panic 片段显示：进程为 `pid 1555: voltageshift`，加载的 Kext 为
`com.sicreative.VoltageShift`，调用路径是
`AnVMSRUserClient::actionMethodRDMSR` → `VoltageShiftAnVMSR::a_rdmsr`；
General Protection Fault 时 `RCX/RSI = 0x776`。这直接证明内核上下文执行了
不受支持的 `RDMSR 0x776`。

对固定上游版本 `xCuri0/VoltageShiftSecure`
`6b4612c004a4631c4c3e4831f2a6989718dea6a5` 的审计解释了该故障：

- `actionMethodRDMSR` 未验证请求，直接调用
  `mDevice->a_rdmsr(msrdata->msr)`。
- `a_rdmsr` 未检查 CPU 能力或寄存器地址，直接执行 `rdmsr64(msr)`。
- `actionMethodWRMSR` 同样把任意地址和值交给 `wrmsr64`。
- 虽然 UserClient 仅允许 root 访问，但这不能使不受支持的 CPU 指令变得安全；
  输入、输出结构体长度也未校验。

不受支持的 MSR 会引发 #GP。不能、也没有使用 C++ 异常来“捕获”内核 #GP。

## 本分支的修复

`voltage20/patch-msr-allowlist.py` 生成的 Kext 采取最小权限策略：

1. 仅接受 Intel family 6、model `0x8c`（Tiger Lake-U）。
2. 仅读取 `0x606`（RAPL 功率单位）和 `0x610`（封装功耗限制）。
3. 仅可写入 `0x610`，且传入值必须与内核重新计算出的“只改 PL1 为 20W”
   完全一致。禁用或锁定时拒绝；不会降低更高的既有上限；写后回读。
4. 任何其他 MSR，包括 `0x776`，都在调用 `rdmsr64` 之前拒绝。
5. CLI 禁止旧的通用 `read`、`write`、电压、Turbo、监控和通用功耗命令。

静态测试只检查源码策略，不访问真实 MSR。新 Kext 尚**未经过实机验证**。

## 仍需提供的证据

在给另两份 Panic 定性前，请先收集三个原始报告。运行
`tools/collect-readonly-diagnostics.sh` 即可；它不访问任何 MSR。对每份报告记录
panic 进程、异常/陷阱、回溯中的 Kext，以及出现时的 MSR 操作数。

## 当前建议与回退

在新构建完成、安装检查表获确认前，保持两个 20W LaunchDaemon 禁用。安装包会备份
被替换的 Kext 和 CLI；明确指定实际生效 EFI 的 `EFI_MOUNT` 后，可用
`uninstall-or-rollback.sh` 恢复。
