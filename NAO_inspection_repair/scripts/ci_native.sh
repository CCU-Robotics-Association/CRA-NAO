#!/bin/bash
# @ Project            : NAO Robot Inspection Toolbox
# @ Description        : Reproducible native SDK and Python setup in CI
# @ Author             : XCrane
set -euo pipefail

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_ROOT="${RUNNER_TEMP:?RUNNER_TEMP is required}/nao-native"
mkdir -p "$BUILD_ROOT"
case "$(uname -s)" in
  Linux)
    BUILD_PLATFORM=linux
    SDK=pynaoqi-python2.7-2.8.6.23-linux64-20191127_152327
    ;;
  Darwin)
    BUILD_PLATFORM=macos
    SDK=pynaoqi-python2.7-2.8.6.23-mac64-20191127_144231
    ;;
  *) printf '%s\n' 'Unsupported build platform' >&2; exit 2 ;;
esac
python3 "$PROJECT_DIR/scripts/fetch_build_inputs.py" --platform "$BUILD_PLATFORM" --output "$BUILD_ROOT"
if [ "$(uname -s)" = Darwin ]; then
  sudo installer -pkg "$BUILD_ROOT/python27.pkg" -target /
  export PYTHON_EXE=/Library/Frameworks/Python.framework/Versions/2.7/bin/python2.7
else
  bash "$BUILD_ROOT/miniconda.sh" -b -p "$BUILD_ROOT/python27"
  export PYTHON_EXE="$BUILD_ROOT/python27/bin/python"
fi
tar -xzf "$BUILD_ROOT/sdk.tar.gz" -C "$BUILD_ROOT"
export PYNAOQI_SDK="$BUILD_ROOT/$SDK"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export PIP_CONFIG_FILE=/dev/null
"$PYTHON_EXE" -m pip --isolated install --index-url https://pypi.org/simple --require-hashes --no-deps --no-cache-dir -r "$PROJECT_DIR/packaging/requirements-bootstrap.lock"
"$PYTHON_EXE" -m pip --isolated install --index-url https://pypi.org/simple --require-hashes --no-deps --no-cache-dir --no-build-isolation --no-use-pep517 -r "$PROJECT_DIR/requirements-build.txt"
if [ "$(uname -s)" = Linux ]; then
  xvfb-run -a /bin/sh "$PROJECT_DIR/build_unix.sh"
else
  /bin/sh "$PROJECT_DIR/build_unix.sh"
fi
