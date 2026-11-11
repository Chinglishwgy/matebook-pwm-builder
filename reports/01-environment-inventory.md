# P0 environment inventory

This workspace is a source checkout, not the affected MateBook installation;
no local EFI, loaded Kext list, launchd state or DiagnosticReports directory is
available here. The following is therefore a transcription of supplied facts,
not a live-machine probe.

| Item | Supplied state | Verification |
| --- | --- | --- |
| CPU | Core i7-1165G7 / Tiger Lake-U | Not live-verified |
| macOS | Sequoia 15.8.1 (24H32) | Not live-verified |
| SMBIOS | MacBookPro16,2 | Not live-verified |
| Bootloader | OpenCore; EFI may be USB | Active EFI unknown |
| Kexts | VoltageShiftSecure, WhateverXe, VoodooI2C/Goodix | Loaded versions unknown |
| LaunchDaemons | `com.matebook.pl1-20`, `com.matebook.mmio-20` disabled and booted out | Not live-verified |
| Pressure workload | No residual `yes` process | Not live-verified |

Use `tools/collect-readonly-diagnostics.sh` on the affected Mac to obtain the
missing evidence. It is deliberately non-mutating and makes no MSR request.
Before any install, mount and explicitly set `EFI_MOUNT` to the confirmed
OpenCore EFI; neither tooling nor this report assumes `/Volumes/EFI` is active.
