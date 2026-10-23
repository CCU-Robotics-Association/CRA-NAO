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
    INSTALLER=Miniconda2-py27_4.8.3-Linux-x86_64.sh
    SDK=pynaoqi-python2.7-2.8.6.23-linux64-20191127_152327
    ;;
  Darwin)
    INSTALLER=Miniconda2-py27_4.8.3-MacOSX-x86_64.sh
    SDK=pynaoqi-python2.7-2.8.6.23-mac64-20191127_144231
    ;;
  *) printf '%s\n' 'Unsupported build platform' >&2; exit 2 ;;
esac
curl --fail --location --retry 3 "https://repo.anaconda.com/miniconda/$INSTALLER" -o "$BUILD_ROOT/miniconda.sh"
bash "$BUILD_ROOT/miniconda.sh" -b -p "$BUILD_ROOT/python27"
curl --fail --location --retry 3 "https://community-static.aldebaran.com/resources/2.8.6/$SDK.tar.gz" -o "$BUILD_ROOT/sdk.tar.gz"
tar -xzf "$BUILD_ROOT/sdk.tar.gz" -C "$BUILD_ROOT"
export PYTHON_EXE="$BUILD_ROOT/python27/bin/python"
export PYNAOQI_SDK="$BUILD_ROOT/$SDK"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
"$PYTHON_EXE" -m pip install 'pip<21' 'setuptools<45' 'wheel==0.34.2'
"$PYTHON_EXE" -m pip install 'PyInstaller==3.6' 'macholib==1.14' 'future==0.18.3'
if [ "$(uname -s)" = Linux ]; then
  xvfb-run -a /bin/sh "$PROJECT_DIR/build_unix.sh"
else
  /bin/sh "$PROJECT_DIR/build_unix.sh"
fi
