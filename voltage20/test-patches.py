#!/usr/bin/env python3
"""Static, hardware-free checks for the source transformations and shell tools."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
vs = root / "vs"

def need(path: Path, text: str) -> None:
    assert text in path.read_text(), f"{text!r} missing from {path}"

def absent(path: Path, text: str) -> None:
    assert text not in path.read_text(), f"unsafe text remains in {path}"

cpp = vs / "VoltageShiftAnVMSR" / "VoltageShfitAnVMSR.cpp"
cli = vs / "VoltageShiftAnVMSR" / "main.mm"
need(cpp, "matebookReadableMSR")
need(cpp, "msr == 0x606 || msr == 0x610")
need(cpp, "request.msr != 0x610")
need(cpp, "request.param != permitted")
need(cpp, "oldRaw > targetRaw")
need(cpp, "inputSize < sizeof(inout)")
need(cli, "disables generic MSR")
absent(cpp, "msrdata->param = mDevice->a_rdmsr(msrdata->msr)")
absent(cpp, "mDevice->a_wrmsr(msrdata->msr, msrdata->param)")
for script in ("auto-20w.sh", "auto-mmio20.sh", "install-20w.sh", "install-mmio-20w.sh", "rollback-mmio-20w.sh", "install.sh", "uninstall-or-rollback.sh", "verify.sh"):
    subprocess.run(["bash", "-n", str(root / "voltage20" / script)], check=True)
print("static policy, source-shape and shell-syntax checks passed")
