#!/usr/bin/env python3
"""Inject a narrow, read-modify-write PL1=20W command into VoltageShiftSecure CLI.

Only MSR 0x610 bits [14:0] are changed, keeping PL2, enable/lock and timing bits.
Abort rather than touching a locked or disabled PL1. No voltage/turbo changes.
"""
from pathlib import Path

src = Path("vs/VoltageShiftAnVMSR/main.mm")
data = src.read_text()
needle = "int setPower(int argc,int p1,int p2){"
assert data.count(needle) == 1, "Unexpected upstream PL1 source layout"
assert data.count('} else if (!strncmp(parameter, "power", 5)){') == 1

injection = r'''
int safeSetPL1_20W() {
    // This function is intentionally restricted to one specific PL1 target.
    if (!connect) {
        printf("PL1_20W_ERROR: VoltageShift IOService is not accessible\n");
        return 2;
    }

    inout request = {};
    inout response = {};
    size_t size = sizeof(response);
    request.action = AnVMSRActionMethodRDMSR;
    request.msr = 0x606; // MSR_RAPL_POWER_UNIT
    kern_return_t status = IOConnectCallStructMethod(
        connect, AnVMSRActionMethodRDMSR,
        &request, sizeof(request), &response, &size);
    if (status != KERN_SUCCESS) {
        printf("PL1_20W_ERROR: Failed reading MSR 0x606 (%x)\n", status);
        return 3;
    }

    const uint64_t exponent = response.param & 0xF;
    if (exponent < 1 || exponent > 12) {
        printf("PL1_20W_ERROR: Unreasonable RAPL power unit exponent %llu\n", exponent);
        return 4;
    }
    const uint64_t rawTarget = 20ULL << exponent;
    if (rawTarget > 0x7FFFULL) {
        printf("PL1_20W_ERROR: PL1 raw value overflow\n");
        return 5;
    }

    request.msr = 0x610; // MSR_PKG_POWER_LIMIT
    response = {};
    size = sizeof(response);
    status = IOConnectCallStructMethod(
        connect, AnVMSRActionMethodRDMSR,
        &request, sizeof(request), &response, &size);
    if (status != KERN_SUCCESS) {
        printf("PL1_20W_ERROR: Failed reading MSR 0x610 (%x)\n", status);
        return 6;
    }

    const uint64_t original = response.param;
    const uint64_t lock = 1ULL << 63;
    const uint64_t pl1Enable = 1ULL << 15;
    const uint64_t pl1Mask = 0x7FFFULL;
    if (original & lock) {
        printf("PL1_20W_LOCKED: MSR 0x610 lock bit is set; not writing\n");
        return 7;
    }
    if (!(original & pl1Enable)) {
        printf("PL1_20W_ERROR: PL1 was not enabled; not changing firmware policy\n");
        return 8;
    }

    const uint64_t target = (original & ~pl1Mask) | rawTarget;
    printf("PL1_20W: Before=0x%016llx, PL1=%.3fW, PL2raw=%llu, target=20W\n",
           original, double(original & pl1Mask) / double(1ULL << exponent),
           (original >> 32) & pl1Mask);
    if (target != original) {
        request.action = AnVMSRActionMethodWRMSR;
        request.param = target;
        response = {};
        size = sizeof(response);
        status = IOConnectCallStructMethod(
            connect, AnVMSRActionMethodWRMSR,
            &request, sizeof(request), &response, &size);
        if (status != KERN_SUCCESS) {
            printf("PL1_20W_ERROR: MSR write failed (%x)\n", status);
            return 9;
        }
    }

    request.action = AnVMSRActionMethodRDMSR;
    request.param = 0;
    response = {};
    size = sizeof(response);
    status = IOConnectCallStructMethod(
        connect, AnVMSRActionMethodRDMSR,
        &request, sizeof(request), &response, &size);
    if (status != KERN_SUCCESS) {
        printf("PL1_20W_ERROR: Readback failed (%x)\n", status);
        return 10;
    }
    const uint64_t actual = response.param;
    printf("PL1_20W: After=0x%016llx, PL1=%.3fW\n",
           actual, double(actual & pl1Mask) / double(1ULL << exponent));
    if ((actual & pl1Mask) != rawTarget) {
        printf("PL1_20W_NOT_APPLIED: Readback differs (MSR/firmware may override)\n");
        return 11;
    }
    if ((actual & ~pl1Mask) != (original & ~pl1Mask)) {
        printf("PL1_20W_ERROR: Unexpected non-PL1 register change\n");
        return 12;
    }
    printf("PL1_20W_OK: PL1=20W, PL2/Turbo/voltage untouched\n");
    return 0;
}

'''
data = data.replace(needle, injection + needle)
old = '} else if (!strncmp(parameter, "power", 5)){'
new = '} else if (!strcmp(parameter, "pl1-20w")){\n            return safeSetPL1_20W();\n        ' + old
data = data.replace(old, new)
assert "PL1_20W_OK" in data
assert data.count("int safeSetPL1_20W()") == 1
src.write_text(data)
print("Safeguarded PL1=20W CLI patch injected into upstream source")
