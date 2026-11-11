# Power-management assessment

## What the supplied measurements demonstrate

The provided register snapshots and load measurements establish that the
previous work changed MSR and MMIO PL1 from 10W to 20W while preserving PL2
(60W), lock state and other protection fields. About 18W package power and
2.95GHz average all-core frequency after a 30-second warm-up are consistent
with a 20W *ceiling*, not evidence of a failed setting. No case has been made
to raise PL1 above 20W or to change PL2, PL4, ICCMAX, PROCHOT or temperature
protection.

`CPU LIMIT PL1` can be historical telemetry; it must not be treated as an
active limiter without a contemporaneous power/frequency measurement.

## Automatic-apply policy in this branch

- Fixed target: 20W only, AC only, i7-1165G7 identity check.
- Kext checks Tiger Lake model, power units, PL1 enable and lock state,
  permitted value range and read-back before writes.
- The MMIO path cross-checks the mapped MMIO power-unit field against MSR
  `0x606`, maps a single page, and changes only PL1 bits 0:14.
- The old five-minute persistent `StartInterval` is removed. The daemon makes
  a single boot-time, idempotent check rather than repeatedly touching
  registers. A later sleep/wake policy requires separate real-hardware
  validation.

This policy intentionally retains the existing MSR/MMIO 20W implementation
instead of adding a second power-management system.

## Validation still required

All rows below are **unverified on hardware** in this workspace.

| Item | Acceptance evidence |
| --- | --- |
| New Kext build | GitHub Actions x86_64 Kext and CLI build artifact, SHA256 passes |
| MSR crash path | New Kext installed; generic CLI command rejected; no `0x776` probe is made |
| PL1/MMIO state | Approved `verify.sh --hardware` output shows allowed MMIO endpoint only |
| Sustained performance | 30s warm-up plus `powermetrics` and normal CPU benchmark on AC |
| Sleep/wake | Several controlled sleep/wake cycles with no WindowServer fault |
| Rollback | Backup folder and USB EFI proven bootable before rollout |

The required test order is baseline first, then the audited 20W build. Record
package power, all-core frequency, temperature and any active limit indication;
do not require exactly 20.00W.
