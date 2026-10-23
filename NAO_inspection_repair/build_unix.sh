#!/bin/sh
# @ Project            : NAO Robot Inspection Toolbox
# @ Description        : Build Linux and macOS native packages
# @ Author             : XCrane
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/scripts/runtime.sh"
exec "$NAO_PYTHON" -B "$SCRIPT_DIR/scripts/build_unix.py" "$@"
