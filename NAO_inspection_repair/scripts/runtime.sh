#!/bin/sh
# @ Project            : NAO Robot Inspection Toolbox
# @ Description        : Shared Python selection for Linux and macOS
# @ Author             : XCrane

if [ -n "${PYTHON_EXE:-}" ]; then
    NAO_PYTHON=$PYTHON_EXE
else
    NAO_PYTHON=
    for candidate in python2.7 python2 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
            "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] != (2, 7))' 2>/dev/null; then
            NAO_PYTHON=$candidate
            break
        fi
    done
fi
if [ -z "$NAO_PYTHON" ]; then
    printf '%s\n' 'Python 2.7 not found. Set PYTHON_EXE to a 64-bit Python 2.7 executable.' >&2
    exit 2
fi
export NAO_PYTHON
