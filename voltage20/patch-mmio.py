#!/usr/bin/env python3
"""Add a *fixed 20W, locked-safe* MCHBAR MMIO RAPL extension to VoltageShiftSecure.

New root-only methods:
  voltageshift mmio-read  - read PCI 00:00.0 MCHBAR + 0x59a0
  voltageshift mmio20     - set only MMIO PL1 15-bit field to 20W and verify.
No generic PCI writes, no high/low lockbit changes, no MMIO disable.
Apply AFTER voltage20/patch-voltageshift.py.
"""
from pathlib import Path

head = Path("vs/VoltageShiftAnVMSR/VoltageShiftAnVMSR.h")
cpp = Path("vs/VoltageShiftAnVMSR/VoltageShfitAnVMSR.cpp")
cli = Path("vs/VoltageShiftAnVMSR/main.mm")
info = Path("vs/VoltageShiftAnVMSR/VoltageShift-Info.plist")

def replace_once(p, old, new):
    s = p.read_text()
    assert s.count(old) == 1, f"unexpected {p}: {old[:75]!r} found {s.count(old)} times"
    p.write_text(s.replace(old, new))

replace_once(head, '#include <IOKit/IOBufferMemoryDescriptor.h>',
'''#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IODeviceMemory.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOIterator.h>''')
replace_once(head, '    virtual IOReturn actionMethodWRMSR(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);',
'''    virtual IOReturn actionMethodWRMSR(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);
    virtual IOReturn actionMethodMMIORAPL(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);''')

replace_once(cpp, '''\tstatic const IOExternalMethod methodDescs[3] = {
\t\t{ NULL, (IOMethod) &AnVMSRUserClient::actionMethodRDMSR, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
\t\t{ NULL, (IOMethod) &AnVMSRUserClient::actionMethodWRMSR, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
\t};''',
'''\tstatic const IOExternalMethod methodDescs[3] = {
\t\t{ NULL, (IOMethod) &AnVMSRUserClient::actionMethodRDMSR, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
\t\t{ NULL, (IOMethod) &AnVMSRUserClient::actionMethodWRMSR, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
        { NULL, (IOMethod) &AnVMSRUserClient::actionMethodMMIORAPL, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
\t};''')

method = r'''
// Tiger Lake-U package RAPL MMIO, Intel Xe MCHBAR PCU_PACKAGE_RAPL_LIMIT +0x59a0.
// The endpoint is root-only because VoltageShiftSecure newUserClient requires root.
// Request: inout.action = 2; param = 0 (read) or 20 (raise PL1 to 20W).
// Reply:   action = 0 (read), 1 (changed), 2 (already >=20W);
//          msr = MCHBAR base; param = full 64-bit MMIO RAPL register.
// NOTE: MMIO write uses only low 32 bits, touching bits 0:14. PL2 / lock /
//       window / enable / clamp all stay untouched. No MMIO Lock or disable.
IOReturn AnVMSRUserClient::actionMethodMMIORAPL(UInt32 *dataIn, UInt32 *dataOut,
                                                IOByteCount inputSize, IOByteCount *outputSize)
{
#if !TARGET_CPU_X86_64
    return kIOReturnUnsupported;
#else
    if (!dataIn || !dataOut || !outputSize ||
        inputSize < sizeof(inout) || *outputSize < sizeof(inout))
        return kIOReturnBadArgument;

    const inout request = *((const inout *)dataIn);
    if (request.action != 2 || (request.param != 0 && request.param != 20))
        return kIOReturnBadArgument;

    // CPU family 6, model 0x8c = Tiger Lake-U; hard fail on other processors.
    uint32_t a=0, b=0, c=0, d=0;
    __asm__ volatile ("cpuid" : "=a"(a), "=b"(b), "=c"(c), "=d"(d) : "a"(1), "c"(0));
    const uint32_t family = (a >> 8) & 0xf;
    const uint32_t model = ((a >> 4) & 0xf) | ((a >> 12) & 0xf0);
    if (family != 6 || model != 0x8c)
        return kIOReturnUnsupported;

    const uint64_t unitsMSR = mDevice->a_rdmsr(0x606);
    const uint32_t unitExp = (uint32_t)(unitsMSR & 0xf);
    if (unitExp < 1 || unitExp > 12)
        return kIOReturnUnsupported;
    const uint32_t targetRaw = 20U << unitExp;
    if (targetRaw > 0x7fffU)
        return kIOReturnUnsupported;

    OSDictionary *match = IOService::serviceMatching("IOPCIDevice");
    if (!match) return kIOReturnNoMemory;
    OSIterator *iter = nullptr;
    const IOReturn finding = IOService::getMatchingServices(match, &iter);
    if (finding != kIOReturnSuccess || !iter) return kIOReturnNotFound;

    uint32_t mchLow = 0, mchHigh = 0;
    bool found = false;
    OSObject *obj = nullptr;
    while ((obj = iter->getNextObject())) {
        IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, obj);
        if (!pci) continue;
        if (pci->getBusNumber() != 0 || pci->getDeviceNumber() != 0 ||
            pci->getFunctionNumber() != 0) continue;
        if (pci->configRead16(0x00) != 0x8086) continue;
        mchLow = pci->configRead32(0x48);
        mchHigh = pci->configRead32(0x4c);
        found = true;
        break;
    }
    iter->release();
    if (!found) return kIOReturnNotFound;
    // v1 deliberately rejects high 32-bit MCHBAR addresses. Never guess.
    if (!(mchLow & 0x1U) || mchHigh != 0)
        return kIOReturnUnsupported;
    const uint64_t mchbar = uint64_t(mchLow & ~1U);
    if ((mchbar & 0xfffU) || mchbar < 0xc0000000ULL ||
        mchbar > 0xfff00000ULL)
        return kIOReturnUnsupported;

    // Map only page [MCHBAR+0x5000, +0x5fff] with uncached device semantics.
    const IOPhysicalAddress phys = (IOPhysicalAddress)(mchbar + 0x5000ULL);
    IODeviceMemory *mem = IODeviceMemory::withRange(phys, 0x1000);
    if (!mem) return kIOReturnNoMemory;
    IOMemoryMap *map = mem->map(kIOMapInhibitCache);
    if (!map) { mem->release(); return kIOReturnNoMemory; }

    const uintptr_t va = (uintptr_t)map->getVirtualAddress();
    if (!va || map->getLength() < 0x9a8) {
        map->release(); mem->release();
        return kIOReturnNoMemory;
    }
    volatile uint32_t *lowAddr = (volatile uint32_t *)(va + 0x9a0);
    volatile uint32_t *highAddr = (volatile uint32_t *)(va + 0x9a4);
    const uint32_t beforeLo = *lowAddr;
    const uint32_t beforeHi = *highAddr;
    const uint64_t before = (uint64_t(beforeHi) << 32) | beforeLo;
    uint32_t resultState = 0;
    IOReturn result = kIOReturnSuccess;

    if (request.param == 20) {
        const uint32_t oldRaw = beforeLo & 0x7fffU;
        const uint32_t oldWatts = oldRaw >> unitExp;
        const bool enabled = (beforeLo & (1U << 15)) != 0;
        const bool locked = (beforeHi & (1U << 31)) != 0;

        // Refuse changes to locked/disabled/suspicious register states.
        if (locked || !enabled || oldWatts < 5 || oldWatts > 28) {
            result = kIOReturnNotPrivileged;
        } else if (oldRaw >= targetRaw) {
            // Do not reduce an existing higher limit.
            resultState = 2;
        } else {
            const uint32_t desiredLo = (beforeLo & ~0x7fffU) | targetRaw;
            *lowAddr = desiredLo;
            __sync_synchronize();
            resultState = 1;
            const uint32_t afterLo = *lowAddr;
            const uint32_t afterHi = *highAddr;
            if ((afterLo & 0x7fffU) != targetRaw ||
                (afterLo & ~0x7fffU) != (beforeLo & ~0x7fffU) ||
                afterHi != beforeHi)
                result = kIOReturnIOError;
        }
    }
    const uint32_t endLo = *lowAddr;
    const uint32_t endHi = *highAddr;
    inout *reply = (inout *)dataOut;
    reply->action = resultState;
    reply->msr = (UInt32)mchbar;
    reply->param = (uint64_t(endHi) << 32) | endLo;
    *outputSize = sizeof(inout);
    map->release();
    mem->release();
    return result;
#endif
}

'''
replace_once(cpp, 'IOReturn AnVMSRUserClient::clientMemoryForType(', method + 'IOReturn AnVMSRUserClient::clientMemoryForType(')

# Link IOPCIFamily, because this Kext now uses IOPCIDevice C++ interfaces.
replace_once(info, '''\t<key>OSBundleLibraries</key>
\t<dict>''', '''\t<key>OSBundleLibraries</key>
\t<dict>
        <key>com.apple.iokit.IOPCIFamily</key>
        <string>2.9</string>''')

cli_source = r'''
int mmioPL1Command(bool write20) {
    if (!service || !connect) {
        printf("MMIO20_ERROR: VoltageShiftSecure Kext not loaded\n");
        return 3;
    }
    inout in = {};
    inout out = {};
    size_t outsize = sizeof(out);
    in.action = 2;
    in.msr = 0;
    in.param = write20 ? 20 : 0;
    const kern_return_t ret = IOConnectCallStructMethod(connect, 2,
                                        &in, sizeof(in), &out, &outsize);
    if (ret != KERN_SUCCESS) {
        printf("MMIO20_ERROR: Kext read/write rejected (IOReturn 0x%08x)\n", ret);
        printf("Possible causes: PCI 00:00.0 not found, MCHBAR disabled, "
               "wrong CPU model, MMIO locked, or physical mapping unsupported\n");
        return 4;
    }
    if (outsize != sizeof(out)) {
        printf("MMIO20_ERROR: Invalid result size\n");
        return 5;
    }
    // MSR power units. Additional read cannot modify registers.
    inout uReq = {};
    inout uOut = {};
    size_t uSize = sizeof(uOut);
    uReq.msr = 0x606;
    if (IOConnectCallStructMethod(connect, 0, &uReq, sizeof(uReq),
                                  &uOut, &uSize) != KERN_SUCCESS)
        return 6;
    const uint32_t exp = (uint32_t)(uOut.param & 0xf);
    if (exp < 1 || exp > 12)
        return 7;
    const uint32_t low = (uint32_t)out.param;
    const uint32_t high = (uint32_t)(out.param >> 32);
    const double watts = double(low & 0x7fffU) / double(1ULL << exp);
    const double pl2watts = double(high & 0x7fffU) / double(1ULL << exp);
    printf("MMIO20: MCHBAR=0x%08x, MMIO_RAPL=0x%016llx\n",
           out.msr, (unsigned long long)out.param);
    printf("MMIO20: PL1=%.3fW enabled=%d, PL2=%.3fW enabled=%d, locked=%d\n",
           watts, !!(low & 0x8000U), pl2watts,
           !!(high & 0x8000U), !!(high & 0x80000000U));
    if (write20) {
        if (watts < 19.99) {
            printf("MMIO20_ERROR: MMIO PL1 did not reach 20 W\n");
            return 8;
        }
        printf("MMIO20_OK: MMIO PL1 >= 20W. PL2/lock/window preserved.\n");
    } else {
        printf("MMIO20_READ_OK: read-only MMIO RAPL inspection successful.\n");
    }
    return 0;
}

'''
replace_once(cli, 'int main(int argc, const char * argv[])', cli_source + 'int main(int argc, const char * argv[])')
replace_once(cli, '''    if (!strncmp(parameter, "info", 4)){''',
'''    if (!strcmp(parameter, "mmio-read")) {
        return mmioPL1Command(false);
    } else if (!strcmp(parameter, "mmio20")) {
        return mmioPL1Command(true);
    } else if (!strncmp(parameter, "info", 4)){''')
print("MMIO20: Mac Tiger Lake MCHBAR extension, root-only read and guarded write injected")
