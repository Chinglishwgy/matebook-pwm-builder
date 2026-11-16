#!/usr/bin/env python3
"""Add *generic* MCHBAR MMIO read/write to VoltageShiftSecure, mirroring the
original MSR read/write commands. No fixed wattage, no fixed register.

New root-only commands:
  voltageshift mmio-read  <HEX_OFFSET> [32|64]
  voltageshift mmio-write <HEX_OFFSET> <HEX_VALUE> [32|64]

Offsets are relative to the PCI 00:00.0 MCHBAR base (Tiger Lake RAPL:
power unit 0x5938, package RAPL limit 0x59a0). Access is bounds-checked
inside a 32 KiB MCHBAR window, naturally aligned, uncached-mapped, and
writes are read back for verification. All original commands stay intact.
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
#include <libkern/c++/OSIterator.h>''')

replace_once(head, '''enum {
    AnVMSRActionMethodRDMSR = 0,
    AnVMSRActionMethodWRMSR = 1,
    AnVMSRNumMethods
};''',
'''enum {
    AnVMSRActionMethodRDMSR = 0,
    AnVMSRActionMethodWRMSR = 1,
    AnVMSRActionMethodMMIO = 2,
    AnVMSRNumMethods
};

// MMIO sub-operations passed in inout.action for AnVMSRActionMethodMMIO.
enum {
    AnVMSRMMIORead32 = 0,
    AnVMSRMMIOWrite32 = 1,
    AnVMSRMMIORead64 = 2,
    AnVMSRMMIOWrite64 = 3
};''')

replace_once(head, '    virtual IOReturn actionMethodWRMSR(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);',
'''    virtual IOReturn actionMethodWRMSR(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);
    virtual IOReturn actionMethodMMIO(UInt32 *dataIn, UInt32 *dataOut, IOByteCount inputSize, IOByteCount *outputSize);''')

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
\t\t{ NULL, (IOMethod) &AnVMSRUserClient::actionMethodMMIO, kIOUCStructIStructO,
            kIOUCVariableStructureSize, kIOUCVariableStructureSize },
\t};''')

method = r'''
// Generic MCHBAR MMIO access, mirroring the RDMSR/WRMSR user methods.
// Root-only: VoltageShiftSecure newUserClient already requires admin.
// Request: action = AnVMSRMMIO{Read,Write}{32,64}; msr = offset from MCHBAR
//          base; param = value to write (ignored for reads).
// Reply:   action = 0 read ok / 1 write applied / 2 write readback mismatch;
//          msr = MCHBAR base (low 32 bits); param = value read or read back.
// Bounds: offset must be naturally aligned and inside the 32 KiB window
// mapped here. Tiger Lake MCHBAR is at least 32 KiB (RAPL sits at 0x59xx),
// so the window never reaches past the BAR. Lock bits are never masked or
// forced: a locked register simply reads back unchanged (status 2).
IOReturn AnVMSRUserClient::actionMethodMMIO(UInt32 *dataIn, UInt32 *dataOut,
                                            IOByteCount inputSize, IOByteCount *outputSize)
{
#if !TARGET_CPU_X86_64
    return kIOReturnUnsupported;
#else
    if (!dataIn || !dataOut || !outputSize ||
        inputSize < sizeof(inout) || *outputSize < sizeof(inout))
        return kIOReturnBadArgument;

    const inout request = *((const inout *)dataIn);
    const uint32_t op = request.action;
    if (op > AnVMSRMMIOWrite64)
        return kIOReturnBadArgument;
    const bool is64 = (op >= AnVMSRMMIORead64);
    const bool isWrite = (op == AnVMSRMMIOWrite32 || op == AnVMSRMMIOWrite64);
    const uint32_t width = is64 ? 8U : 4U;
    const uint32_t offset = request.msr;
    const uint32_t window = 0x8000U;
    if ((offset & (width - 1U)) || offset > window - width)
        return kIOReturnBadArgument;

    // Intel family 6 only; MCHBAR layout is Intel host-bridge specific.
    uint32_t a=0, b=0, c=0, d=0;
    __asm__ volatile ("cpuid" : "=a"(a), "=b"(b), "=c"(c), "=d"(d) : "a"(1), "c"(0));
    if (((a >> 8) & 0xf) != 6)
        return kIOReturnUnsupported;

    // match/iter are OSPtr on the modern macOS SDK: automatic cleanup, never
    // call ->release() on them (over-release panics). Same convention as the
    // proven voltage20/patch-mmio.py.
    auto match = IOService::serviceMatching("IOPCIDevice");
    if (!match) return kIOReturnNoMemory;
    auto iter = IOService::getMatchingServices(match);
    if (!iter) return kIOReturnNotFound;

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
    if (!found) return kIOReturnNotFound;
    // Reject disabled MCHBAR or addresses above 4 GiB. Never guess.
    if (!(mchLow & 0x1U) || mchHigh != 0)
        return kIOReturnUnsupported;
    const uint64_t mchbar = uint64_t(mchLow & ~1U);
    if ((mchbar & 0xfffU) || mchbar < 0xc0000000ULL || mchbar > 0xfff00000ULL)
        return kIOReturnUnsupported;

    // withRange hands back a retained raw IODeviceMemory; map() returns an
    // OSPtr<IOMemoryMap> which retains its descriptor. Release the raw owner.
    auto mem = IODeviceMemory::withRange((IOPhysicalAddress)mchbar, window);
    if (!mem) return kIOReturnNoMemory;
    auto map = mem->map(kIOMapInhibitCache);
    mem->release();
    if (!map) return kIOReturnNoMemory;
    const uintptr_t va = (uintptr_t)map->getVirtualAddress();
    if (!va || map->getLength() < window)
        return kIOReturnNoMemory;

    uint64_t value = 0;
    uint32_t status = 0;
    if (!isWrite) {
        if (is64)
            value = *(volatile uint64_t *)(va + offset);
        else
            value = *(volatile uint32_t *)(va + offset);
    } else {
        const uint64_t writeVal = request.param;
        if (is64)
            *(volatile uint64_t *)(va + offset) = writeVal;
        else
            *(volatile uint32_t *)(va + offset) = (uint32_t)writeVal;
        __sync_synchronize();
        uint64_t readback;
        if (is64)
            readback = *(volatile uint64_t *)(va + offset);
        else
            readback = *(volatile uint32_t *)(va + offset);
        value = readback;
        const uint64_t mask = is64 ? ~0ULL : 0xffffffffULL;
        status = ((readback & mask) == (writeVal & mask)) ? 1U : 2U;
    }

    inout *reply = (inout *)dataOut;
    reply->action = status;
    reply->msr = (UInt32)mchbar;
    reply->param = value;
    *outputSize = sizeof(inout);
    return kIOReturnSuccess;
#endif
}

'''
replace_once(cpp, 'IOReturn AnVMSRUserClient::clientMemoryForType(', method + 'IOReturn AnVMSRUserClient::clientMemoryForType(')

# Link IOPCIFamily, because this Kext now uses IOPCIDevice C++ interfaces.
replace_once(info, '''\t<key>OSBundleLibraries</key>
\t<dict>''', '''\t<key>OSBundleLibraries</key>
\t<dict>
\t\t<key>com.apple.iokit.IOPCIFamily</key>
\t\t<string>2.9</string>''')

# main.mm keeps its own copy of the method enum; extend it too.
replace_once(cli, '''enum {
    AnVMSRActionMethodRDMSR = 0,
    AnVMSRActionMethodWRMSR = 1,
    AnVMSRNumMethods
};''',
'''enum {
    AnVMSRActionMethodRDMSR = 0,
    AnVMSRActionMethodWRMSR = 1,
    AnVMSRActionMethodMMIO = 2,
    AnVMSRNumMethods
};

enum {
    AnVMSRMMIORead32 = 0,
    AnVMSRMMIOWrite32 = 1,
    AnVMSRMMIORead64 = 2,
    AnVMSRMMIOWrite64 = 3
};''')

cli_source = r'''
// Generic MCHBAR MMIO read/write, analogous to the MSR read/write commands.
int mmioAccess(bool isWrite, int argc, const char *argv[]) {
    if (!service || !connect) {
        printf("MMIO_ERROR: VoltageShift Kext not loaded\n");
        return 3;
    }
    if (argc < 3) {
        printf("MMIO_ERROR: missing HEX_OFFSET (relative to MCHBAR)\n");
        return 2;
    }
    const uint32_t offset = (uint32_t)hex2int(argv[2]);
    uint64_t value = 0;
    int width = 32;
    if (isWrite) {
        if (argc < 4) {
            printf("MMIO_ERROR: missing HEX_VALUE\n");
            return 2;
        }
        value = hex2int(argv[3]);
        if (argc >= 5) width = atoi(argv[4]);
    } else {
        if (argc >= 4) width = atoi(argv[3]);
    }
    if (width != 32 && width != 64) {
        printf("MMIO_ERROR: width must be 32 or 64\n");
        return 2;
    }
    const bool is64 = (width == 64);
    inout in = {};
    inout out = {};
    size_t outsize = sizeof(out);
    in.action = (is64 ? AnVMSRMMIORead64 : AnVMSRMMIORead32) + (isWrite ? 1 : 0);
    in.msr = offset;
    in.param = value;
    const kern_return_t ret = IOConnectCallStructMethod(connect, AnVMSRActionMethodMMIO,
                                        &in, sizeof(in), &out, &outsize);
    if (ret != KERN_SUCCESS) {
        printf("MMIO_ERROR: kext rejected request (IOReturn 0x%08x)\n", ret);
        printf("Possible causes: no Intel 00:00.0 host bridge, MCHBAR disabled or above 4GB,\n");
        printf("offset unaligned or outside the 32KB MCHBAR window\n");
        return 4;
    }
    if (outsize != sizeof(out)) {
        printf("MMIO_ERROR: invalid result size\n");
        return 5;
    }
    const uint64_t mchbar = out.msr;
    const uint64_t result = out.param;
    printf("MMIO: MCHBAR=0x%08llx offset=0x%04x phys=0x%08llx width=%d\n",
           (unsigned long long)mchbar, offset,
           (unsigned long long)(mchbar + offset), width);
    if (!isWrite) {
        if (is64)
            printf("MMIO_READ: [0x%04x] = 0x%016llx\n", offset, (unsigned long long)result);
        else
            printf("MMIO_READ: [0x%04x] = 0x%08llx\n", offset, (unsigned long long)(uint32_t)result);
        // Read-only convenience decode of Tiger Lake RAPL registers.
        if (offset == 0x5938) {
            printf("MMIO_READ: RAPL power unit: power=1/2^%u W, energy=1/2^%u J, time=1/2^%u s\n",
                   (unsigned)(result & 0xf), (unsigned)((result >> 8) & 0x1f),
                   (unsigned)((result >> 16) & 0xf));
        } else if (offset == 0x59a0 && is64) {
            inout uReq = {};
            inout uOut = {};
            size_t uSize = sizeof(uOut);
            uReq.action = AnVMSRActionMethodRDMSR;
            uReq.msr = 0x606;
            if (IOConnectCallStructMethod(connect, AnVMSRActionMethodRDMSR,
                                          &uReq, sizeof(uReq), &uOut, &uSize) == KERN_SUCCESS) {
                const uint32_t exp = (uint32_t)(uOut.param & 0xf);
                if (exp >= 1 && exp <= 12) {
                    const uint32_t lo = (uint32_t)result;
                    const uint32_t hi = (uint32_t)(result >> 32);
                    const double unit = double(1ULL << exp);
                    printf("MMIO_READ: PL1=%.3fW enabled=%d, PL2=%.3fW enabled=%d, locked=%d\n",
                           double(lo & 0x7fffU) / unit, !!(lo & 0x8000U),
                           double(hi & 0x7fffU) / unit, !!(hi & 0x8000U),
                           !!(hi & 0x80000000U));
                }
            }
        }
        return 0;
    }
    if (is64)
        printf("MMIO_WRITE: [0x%04x] <= 0x%016llx, readback=0x%016llx %s\n",
               offset, (unsigned long long)value, (unsigned long long)result,
               out.action == 1 ? "OK" : "MISMATCH (locked or firmware overridden)");
    else
        printf("MMIO_WRITE: [0x%04x] <= 0x%08llx, readback=0x%08llx %s\n",
               offset, (unsigned long long)(uint32_t)value,
               (unsigned long long)(uint32_t)result,
               out.action == 1 ? "OK" : "MISMATCH (locked or firmware overridden)");
    return out.action == 1 ? 0 : 6;
}

'''
replace_once(cli, 'int main(int argc, const char * argv[])', cli_source + 'int main(int argc, const char * argv[])')
replace_once(cli, '''    if (!strncmp(parameter, "info", 4)){''',
'''    if (!strcmp(parameter, "mmio-read")) {
        return mmioAccess(false, argc, argv);
    } else if (!strcmp(parameter, "mmio-write")) {
        return mmioAccess(true, argc, argv);
    } else if (!strncmp(parameter, "info", 4)){''')
replace_once(cli, '''    printf("write MSR: %s write <HEX_MSR> <HEX_VALUE>\\n\\n", name);''',
'''    printf("write MSR: %s write <HEX_MSR> <HEX_VALUE>\\n\\n", name);
    printf("read MMIO (MCHBAR offset): %s mmio-read <HEX_OFFSET> [32|64]\\n\\n", name);
    printf("write MMIO (MCHBAR offset): %s mmio-write <HEX_OFFSET> <HEX_VALUE> [32|64]\\n\\n", name);''')
print("MMIO generic: root-only parameterized MCHBAR read/write injected, original commands untouched")