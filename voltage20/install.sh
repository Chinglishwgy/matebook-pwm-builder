#!/bin/bash
# Deliberately explicit wrapper: never guesses /Volumes/EFI.
set -euo pipefail
: "${EFI_MOUNT:?Set EFI_MOUNT to the already-mounted OpenCore EFI you have confirmed is active.}"
case "$EFI_MOUNT" in /*) ;; *) echo "EFI_MOUNT must be an absolute mount path"; exit 64;; esac
exec "$(cd "$(dirname "$0")" && pwd)/install-mmio-20w.sh"
