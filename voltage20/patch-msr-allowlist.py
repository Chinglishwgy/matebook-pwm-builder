#!/usr/bin/env python3
"""Replace VoltageShiftSecure's arbitrary-MSR UserClient with a narrow policy.

The pinned upstream driver passes an untrusted MSR number directly to rdmsr64()
and an untrusted value directly to wrmsr64().  An unsupported RDMSR raises #GP
in kernel context; it cannot be made safe with a C++ exception handler.

This patch intentionally supports only the two MSRs needed by the MateBook's
fixed, Tiger Lake-U PL1=20W operation:
  * 0x606 MSR_RAPL_POWER_UNIT: read-only
  * 0x610 MSR_PKG_POWER_LIMIT: read-only, or a verified PL1-only 20W write
Everything else, including 0x776 and the old voltage/turbo commands, is
rejected before the CPU instruction is issued.
"""
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"unexpected {path}: expected one matching block, got {count}"
    path.write_text(text.replace(old, new))


cpp = Path("vs/VoltageShiftAnVMSR/VoltageShfitAnVMSR.cpp")
old = cpp.read_text()
start = old.index("IOReturn AnVMSRUserClient::actionMethodRDMSR(")
end = old.index("IOReturn AnVMSRUserClient::clientMemoryForType(", start)
replacement = r'''// The CPU instruction is deliberately reachable only through these two
// predicates.  Do not turn this into a generic MSR interface: unsupported MSRs
// cause a #GP in kernel context and can panic macOS.
static bool matebookIsTigerLakeU()
{
#if !TARGET_CPU_X86_64
    return false;
#else
    uint32_t a = 0, b = 0, c = 0, d = 0;
    __asm__ volatile ("cpuid" : "=a"(a), "=b"(b), "=c"(c), "=d"(d)
                      : "a"(1), "c"(0));
    const uint32_t family = (a >> 8) & 0xf;
    const uint32_t model = ((a >> 4) & 0xf) | ((a >> 12) & 0xf0);
    return family == 6 && model == 0x8c;
#endif
}

static bool matebookReadableMSR(uint32_t msr)
{
    return msr == 0x606 || msr == 0x610;
}

IOReturn AnVMSRUserClient::actionMethodRDMSR(UInt32 *dataIn, UInt32 *dataOut,
                                               IOByteCount inputSize,
                                               IOByteCount *outputSize)
{
    if (!mDevice || !dataIn || !dataOut || !outputSize ||
        inputSize < sizeof(inout) || *outputSize < sizeof(inout))
        return kIOReturnBadArgument;
    if (!matebookIsTigerLakeU() || !matebookReadableMSR(((const inout *)dataIn)->msr))
        return kIOReturnUnsupported;

    const inout request = *((const inout *)dataIn);
    inout *reply = (inout *)dataOut;
    *reply = request;
    // request.msr has passed the exact allow-list check above.
    reply->param = mDevice->a_rdmsr(request.msr);
    *outputSize = sizeof(inout);
    return kIOReturnSuccess;
}

IOReturn AnVMSRUserClient::actionMethodWRMSR(UInt32 *dataIn, UInt32 *dataOut,
                                               IOByteCount inputSize,
                                               IOByteCount *outputSize)
{
    if (!mDevice || !dataIn || !dataOut || !outputSize ||
        inputSize < sizeof(inout) || *outputSize < sizeof(inout))
        return kIOReturnBadArgument;
    const inout request = *((const inout *)dataIn);
    if (!matebookIsTigerLakeU() || request.msr != 0x610)
        return kIOReturnUnsupported;

    // 0x606 is allow-listed above and supplies the RAPL power-unit exponent.
    const uint64_t units = mDevice->a_rdmsr(0x606);
    const uint32_t exponent = (uint32_t)(units & 0xf);
    if (exponent < 1 || exponent > 12)
        return kIOReturnUnsupported;
    const uint64_t targetRaw = 20ULL << exponent;
    if (targetRaw > 0x7fffULL)
        return kIOReturnUnsupported;

    // 0x610 is allow-listed. Re-read in kernel to prevent a user-space TOCTOU
    // or a forged write value from changing PL2, lock, clamp, enable or window.
    const uint64_t before = mDevice->a_rdmsr(0x610);
    const uint64_t pl1Mask = 0x7fffULL;
    const uint64_t permitted = (before & ~pl1Mask) | targetRaw;
    const bool locked = (before & (1ULL << 63)) != 0;
    const bool enabled = (before & (1ULL << 15)) != 0;
    const uint64_t oldRaw = before & pl1Mask;
    if (locked || !enabled || oldRaw < (5ULL << exponent) || oldRaw > targetRaw ||
        request.param != permitted)
        return kIOReturnNotPrivileged;

    if (before != permitted)
        mDevice->a_wrmsr(0x610, permitted); // Fixed MSR and fixed PL1 field only.
    const uint64_t after = mDevice->a_rdmsr(0x610);
    if (after != permitted)
        return kIOReturnIOError;

    inout *reply = (inout *)dataOut;
    *reply = request;
    reply->param = after;
    *outputSize = sizeof(inout);
    return kIOReturnSuccess;
}
'''
cpp.write_text(old[:start] + replacement + old[end:])

cli = Path("vs/VoltageShiftAnVMSR/main.mm")
cli_text = cli.read_text()
usage_start = cli_text.index("void usage(const char *name)\n{")
usage_end = cli_text.index("\n}\n\nunsigned long long hex2int", usage_start) + 2
usage_new = '''void usage(const char *name)
{
    printf("This MateBook build intentionally exposes no generic MSR access.\\n");
    printf("Supported commands:\\n");
    printf("    sudo %s pl1-20w    # fixed Tiger Lake PL1=20W, MSR only\\n", name);
    printf("    sudo %s mmio-read  # guarded MMIO RAPL read\\n", name);
    printf("    sudo %s mmio20     # fixed guarded MMIO PL1=20W\\n", name);
}'''
cli.write_text(cli_text[:usage_start] + usage_new + cli_text[usage_end:])

# Block dispatch before any legacy voltage, turbo, monitor, read or write code
# is reached. The Kext independently enforces the same policy.
guard = '''        parameter = (char *)argv[1];
        if (strcmp(parameter, "pl1-20w") && strcmp(parameter, "mmio-read") &&
            strcmp(parameter, "mmio20") && strcmp(parameter, "help")) {
            fprintf(stderr, "This MateBook build disables generic MSR, voltage, turbo and power commands.\\n");
            usage(argv[0]);
            return 64;
        }
'''
replace_once(cli, '        parameter = (char *)argv[1];', guard)

for token in ("matebookReadableMSR", "request.msr != 0x610", "generic MSR"):
    assert token in cpp.read_text() + cli.read_text()
print("Installed Tiger Lake fixed-PL1 MSR allow-list and disabled legacy CLI paths")
