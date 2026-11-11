# P0 kernel-panic analysis

See [kernel-panic-root-cause.md](kernel-panic-root-cause.md) for the complete
analysis. The only panic with supplied evidence is the 19:25:12 general
protection fault in VoltageShift when executing `RDMSR 0x776`. The other two
named kernel panic files have not been supplied and must be read before being
grouped with this failure.
