# WindowServer watchdog assessment

Status: **not determined — the referenced `.panic`, `.ips`, `.spin`, sleep/wake
and shutdown reports were not provided.**

The supplied excerpt (`watchdogd`, “no successful checkins from WindowServer”,
two induced crashes in 120 seconds) establishes only the terminal watchdog
condition: WindowServer stopped checking in. It does not identify the blocking
component. This is categorically different from the documented VoltageShift
general-protection fault.

## Hypotheses, not conclusions

| Hypothesis | Evidence currently available | Evidence needed |
| --- | --- | --- |
| Intel display pipeline / WhateverXe compatibility | None | WindowServer `.ips`, watchdog `.spin`, loaded WhateverXe version, GPU/IGPU stack in a matching kernel backtrace |
| Sleep/wake display reinitialisation failure | None | Timestamp correlation with `pmset -g log`, Sleep Wake Failure diagnostics and display wake events |
| CPU/power-management starvation | None | Correlation with the power daemon logs and a responsive kernel / blocked WindowServer stack |
| Generic system/application stall | None | Full WindowServer thread stacks and unified log time window |

Do not disable GPU acceleration or remove `-wex-tgl-blfull`; neither has been
implicated. Do not remove `-vi2c-force-polling` either. Obtain the reports with
the read-only collector, then compare their timestamps with power/sleep events.

## Low-risk next evidence set

1. Run `tools/collect-readonly-diagnostics.sh` after the next incident.
2. Preserve `WindowServer*.ips`, watchdog spin reports, sleep/wake diagnostics
   and shutdown stalls unchanged.
3. Record the installed/loaded WhateverXe build, OpenCore version and display
   connector configuration; do not change them merely to gather evidence.
4. If a controlled test is approved later, use one change per boot and retain a
   known-good USB EFI. No experiment in this repository modifies those boot
   arguments.
