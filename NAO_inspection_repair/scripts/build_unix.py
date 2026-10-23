# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : Linux 与 macOS 原生构建、验证及归档
@ Author             : XCrane
"""
from __future__ import print_function, unicode_literals
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from unix_runtime import environment


def main():
    if sys.platform not in ("linux", "linux2", "darwin"):
        raise RuntimeError("Build this package on Linux or macOS.")
    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError("The legacy NAOqi SDK requires an x86_64 build environment.")
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = environment()
    subprocess.check_call([sys.executable, "-B", "-m", "PyInstaller", "--noconfirm",
                           os.path.join(project, "nao_toolbox.spec")], cwd=project, env=env)
    sys.path.insert(0, project)
    from nao_diag import __version__
    mac = sys.platform == "darwin"
    artifact = "NAO_Toolbox.app" if mac else "NAO_Toolbox"
    dist = os.path.join(project, "dist", artifact)
    executable = os.path.join(dist, "Contents", "MacOS", "NAO_Toolbox") if mac else dist
    report = os.path.join(project, "build", "native-runtime-check.json")
    clean_env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYNAOQI_SDK", "QI_SDK_PREFIX",
                "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH",
                "TCL_LIBRARY", "TK_LIBRARY", "CONDA_PREFIX", "CONDA_DEFAULT_ENV"):
        clean_env.pop(key, None)
    clean_env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    subprocess.check_call([executable, "--check-runtime", report], env=clean_env, cwd=project)
    with open(report, "rb") as handle:
        result = json.load(handle)
    if not result.get("ok") or not result.get("frozen") or "_MEI" not in result.get("sdk", ""):
        raise RuntimeError("The bundled runtime check failed: %s" % report)
    name = "NAO_Toolbox-%s-%s-x86_64" % (__version__, "macos" if mac else "linux")
    release = os.path.join(project, "release")
    if not os.path.isdir(release):
        os.makedirs(release)
    archive_path = os.path.join(release, name + ".tar.gz")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(dist, arcname=os.path.join(name, artifact))
        archive.add(os.path.join(project, "config.example.json"), arcname=name + "/config.example.json")
        archive.add(os.path.join(project, "docs"), arcname=name + "/docs")
        archive.add(os.path.join(project, "packaging", "UNIX_USAGE.txt"), arcname=name + "/USAGE.txt")
    print("Native runtime check passed. Package: %s" % archive_path)


if __name__ == "__main__":
    main()
