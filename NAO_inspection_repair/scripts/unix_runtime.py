# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : Linux 与 macOS 的 SDK 路径和启动环境
@ Author             : XCrane
"""
from __future__ import print_function, unicode_literals
import os
import struct
import sys


def sdk_paths(candidate):
    if not candidate:
        raise ValueError("Set PYNAOQI_SDK to the vendor SDK directory.")
    candidate = os.path.abspath(os.path.expanduser(candidate))
    paths = (candidate, os.path.join(candidate, "lib"),
             os.path.join(candidate, "lib", "python2.7", "site-packages"),
             os.path.join(candidate, "python2.7", "site-packages"))
    python_dir = next((path for path in paths
                       if os.path.isfile(os.path.join(path, "naoqi.py"))), None)
    if python_dir is None:
        raise ValueError("No naoqi.py found in SDK: %s" % candidate)
    if os.path.basename(python_dir) == "site-packages":
        library_dir = os.path.dirname(os.path.dirname(python_dir))
    elif os.path.basename(python_dir) == "lib":
        library_dir = python_dir
    else:
        library_dir = python_dir
    sdk_root = os.path.dirname(library_dir) if os.path.basename(library_dir) == "lib" else library_dir
    return sdk_root, python_dir, library_dir


def environment(candidate=None):
    if sys.version_info[:2] != (2, 7) or struct.calcsize("P") != 8:
        raise ValueError("The NAOqi 2.8 SDK requires 64-bit Python 2.7.")
    root, python_dir, library_dir = sdk_paths(candidate or os.environ.get("PYNAOQI_SDK"))
    env = dict(os.environ)
    env["PYNAOQI_SDK"] = root
    env["QI_SDK_PREFIX"] = root
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key, value in (("PYTHONPATH", python_dir), ("PATH", os.path.join(root, "bin")),
                       ("LD_LIBRARY_PATH", library_dir), ("DYLD_LIBRARY_PATH", library_dir)):
        env[key] = value + (os.pathsep + env[key] if env.get(key) else "")
    return env


def main():
    try:
        env = environment()
        project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gui = len(sys.argv) > 1 and sys.argv[1] == "--gui"
        arguments = sys.argv[2:] if gui else sys.argv[1:]
        script = os.path.join(project, "nao_gui.py" if gui else "nao_diagnostic.py")
        os.execve(sys.executable, [sys.executable, "-B", script] + arguments, env)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
