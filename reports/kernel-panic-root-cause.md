# VoltageShift kernel panic: root-cause assessment

Status: **confirmed for `Kernel-2026-11-11-192512.panic` from the supplied
excerpt; other panic files are not available in this workspace and remain
unverified.**

## Confirmed causal path

The supplied panic excerpt names `pid 1555: voltageshift`, the
`com.sicreative.VoltageShift` Kext, and the path
`AnVMSRUserClient::actionMethodRDMSR` → `VoltageShiftAnVMSR::a_rdmsr`, with
`RCX/RSI = 0x776` at a general-protection fault. This is direct evidence of an
unsupported `RDMSR 0x776` executed in kernel context.

Audit of the pinned upstream source (`xCuri0/VoltageShiftSecure`
`6b4612c004a4631c4c3e4831f2a6989718dea6a5`) explains the failure:

- `actionMethodRDMSR` dereferences an unvalidated request and invokes
  `mDevice->a_rdmsr(msrdata->msr)`.
- `a_rdmsr` calls `rdmsr64(msr)` without a capability or address check.
- `actionMethodWRMSR` likewise sends an arbitrary request directly to
  `wrmsr64`.
- The root-only UserClient check limits callers, but does not make unsupported
  CPU instructions safe. Neither input/output structure size is validated.

An unsupported MSR can raise #GP; a C++ exception handler is not a valid
kernel recovery mechanism and is not used here.

## Remediation implemented in this branch

`voltage20/patch-msr-allowlist.py` changes the generated Kext so that it:

1. Requires Intel family 6, model `0x8c` (Tiger Lake-U).
2. Permits reads only of `0x606` (RAPL units) and `0x610` (package power
   limit).
3. Permits writes only to `0x610`, only when the supplied value exactly equals
   a kernel-recomputed PL1=20W update. It preserves every other bit, rejects a
   disabled/locked limit, does not reduce a higher existing limit, and checks
   read-back.
4. Rejects every other MSR, including `0x776`, before `rdmsr64` is called.
5. Rejects legacy generic `read`, `write`, voltage, turbo, monitor and general
   power CLI commands before they reach the driver.

Static tests inspect this policy without accessing any real MSR. Hardware
validation of the new Kext is **not yet performed**.

## Unverified evidence required

Collect the three raw panic reports before assigning the same cause to the
other two. Use `tools/collect-readonly-diagnostics.sh`; it never accesses MSRs.
For each report, record panicked process, exception/trap, backtrace extension,
and the actual MSR operand if present.

## Recovery

Keep both 20W LaunchDaemons disabled until the new artifact is built and the
installation checklist is approved. The package backs up the replaced Kext and
CLI; `uninstall-or-rollback.sh` restores them after the active EFI is supplied
explicitly via `EFI_MOUNT`.
