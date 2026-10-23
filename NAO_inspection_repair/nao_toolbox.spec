# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : PyInstaller 图形界面与 NAOqi SDK 打包配置
@ Author             : XCrane
"""

import os
import re

block_cipher = None
project_dir = os.path.abspath(SPECPATH)
sdk_dir = os.environ.get("PYNAOQI_SDK", "")
if os.path.isfile(os.path.join(sdk_dir, "lib", "naoqi.py")):
    sdk_dir = os.path.join(sdk_dir, "lib")
if not os.path.isfile(os.path.join(sdk_dir, "naoqi.py")):
    raise SystemExit("PYNAOQI_SDK must point to the pynaoqi lib directory")


def include_sdk_binary(filename):
    lower = filename.lower()
    if not lower.endswith((".dll", ".pyd")):
        return False
    if lower == "python27.dll":
        return False
    if ("-gd-" in lower or lower.endswith("_d.dll") or
            lower.endswith("_d.pyd") or lower == "zlibd.dll"):
        return False
    if re.search(r"opencv_.+\d+d\.dll$", lower):
        return False
    return True


sdk_binaries = [
    (os.path.join(sdk_dir, name), ".")
    for name in os.listdir(sdk_dir)
    if include_sdk_binary(name)
]

a = Analysis(
    [os.path.join(project_dir, "nao_gui.py")],
    pathex=[project_dir, sdk_dir],
    binaries=sdk_binaries,
    datas=[
        (os.path.join(project_dir, "config.example.json"), "."),
        (os.path.join(project_dir, "docs"), "docs"),
    ],
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
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NAO_Toolbox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
)
