#!/bin/sh
# @ Project            : NAO Robot Inspection Toolbox
# @ Description        : Launch command-line inspection on Linux and macOS
# @ Author             : XCrane
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/scripts/runtime.sh"
exec "$NAO_PYTHON" -B "$SCRIPT_DIR/scripts/unix_runtime.py" "$@"
