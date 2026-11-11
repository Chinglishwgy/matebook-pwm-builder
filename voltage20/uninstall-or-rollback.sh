#!/bin/bash
set -euo pipefail
: "${EFI_MOUNT:?Set EFI_MOUNT to the already-mounted OpenCore EFI you have confirmed is active.}"
exec "$(cd "$(dirname "$0")" && pwd)/rollback-mmio-20w.sh" "$@"
