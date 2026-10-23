# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : PyInstaller 图形界面与 NAOqi SDK 打包配置
@ Author             : XCrane
"""

import os
import re
import sys
import subprocess

# PyInstaller 3.6 无法解析新版 ldconfig 输出末尾的说明行。
if sys.platform.startswith("linux"):
    from distutils.spawn import find_executable
    from PyInstaller.depend import utils as dependency_utils
    cache = {}
    ldconfig = find_executable("ldconfig") or find_executable("ldconfig", "/sbin:/usr/sbin")
    if ldconfig:
        output = subprocess.check_output([ldconfig, "-p"]).decode("utf-8", "replace")
        for line in output.splitlines():
            match = re.match(r"^\s+(\S+)\s+\([^)]*\)\s+=>\s+(\S+)", line)
            if match:
                cache.setdefault(match.group(1), match.group(2))
    dependency_utils.LDCONFIG_CACHE = cache

block_cipher = None
project_dir = os.path.abspath(SPECPATH)
sdk_root = os.path.abspath(os.environ.get("PYNAOQI_SDK", ""))
candidates = [sdk_root, os.path.join(sdk_root, "lib"),
              os.path.join(sdk_root, "lib", "python2.7", "site-packages"),
              os.path.join(sdk_root, "python2.7", "site-packages")]
sdk_dir = next((path for path in candidates if os.path.isfile(os.path.join(path, "naoqi.py"))), None)
if sdk_dir is None:
    raise SystemExit("PYNAOQI_SDK must point to the matching platform SDK")
if os.path.basename(sdk_dir) == "site-packages":
    sdk_library_dir = os.path.dirname(os.path.dirname(sdk_dir))
else:
    sdk_library_dir = sdk_dir


def include_sdk_binary(filename):
    lower = filename.lower()
    native = (lower.endswith((".dll", ".pyd", ".dylib", ".so")) or ".so." in lower)
    if not native or lower.startswith(("python27.dll", "libpython2.7")):
        return False
    if ("-gd-" in lower or lower.endswith("_d.dll") or
            lower.endswith(("_d.pyd", "_d.so", "_d.dylib", "-d.dylib")) or lower == "zlibd.dll"):
        return False
    if re.search(r"opencv_.+\d+d\.dll$", lower):
        return False
    return True


sdk_binaries = []
for directory, subdirectories, filenames in os.walk(sdk_library_dir):
    subdirectories[:] = [name for name in subdirectories
                         if not name.endswith(".dSYM") and name not in ("__pycache__", "cmake")]
    for name in filenames:
        if include_sdk_binary(name):
            if os.path.normcase(os.path.abspath(directory)) == os.path.normcase(sdk_dir):
                destination = "."
            else:
                destination = os.path.relpath(directory, sdk_library_dir)
            sdk_binaries.append((os.path.join(directory, name), destination))

package_data = [
    (os.path.join(project_dir, "config.example.json"), "."),
    (os.path.join(project_dir, "docs"), "docs"),
]
if sys.platform == "darwin":
    # Python.org 的 Tk 是 dylib，并非旧 hook 假定的独立 Tcl/Tk framework。
    import Tkinter
    tcl_root = Tkinter.Tcl().eval("info library")
    tk_root = os.path.join(os.path.dirname(tcl_root), "tk" + str(Tkinter.TkVersion))
    for directory, filename, destination in ((tcl_root, "init.tcl", "tcl"),
                                              (tk_root, "tk.tcl", "tk")):
        if not os.path.isfile(os.path.join(directory, filename)):
            raise SystemExit("Missing Tk runtime data: " + directory)
        package_data.append((directory, destination))

a = Analysis(
    [os.path.join(project_dir, "nao_gui.py")],
    pathex=[project_dir, sdk_dir],
    binaries=sdk_binaries,
    datas=package_data,
    hiddenimports=[
        "naoqi", "qi", "inaoqi", "_inaoqi", "_qi",
        "allog", "_allog", "motion", "vision_definitions",
        "Tkinter", "ttk", "tkFileDialog", "tkMessageBox", "tkSimpleDialog",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
if sys.platform == "darwin":
    with open(os.path.join(project_dir, "nao_diag", "__init__.py"), "rb") as handle:
        version = re.search(br'__version__\s*=\s*"([^"]+)"', handle.read()).group(1).decode("ascii")
    executable = EXE(pyz, a.scripts, [], exclude_binaries=True,
                     name="NAO_Toolbox", debug=False, strip=False, upx=False, console=False)
    collected = COLLECT(executable, a.binaries, a.zipfiles, a.datas,
                        name="NAO_Toolbox", strip=False, upx=False)
    app = BUNDLE(collected, name="NAO_Toolbox.app",
                 version=version,
                 bundle_identifier="org.ccu-robotics.nao-toolbox",
                 info_plist={"NSHighResolutionCapable": True,
                             "CFBundleExecutable": "NAO_Toolbox"})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
              name="NAO_Toolbox", debug=False, bootloader_ignore_signals=False,
              strip=False, upx=False, runtime_tmpdir=None, console=False)
