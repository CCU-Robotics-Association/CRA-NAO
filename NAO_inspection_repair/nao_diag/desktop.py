# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : Windows、Linux 与 macOS 桌面文件和字体适配
@ Author             : XCrane
"""
from __future__ import unicode_literals
import os
import subprocess
import sys


def log_directory():
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or home
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Logs")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    return os.path.join(base, "NAO_Toolbox")


def open_path(path):
    path = os.path.abspath(path)
    if sys.platform == "win32":
        os.startfile(path)
        return
    command = "open" if sys.platform == "darwin" else "xdg-open"
    with open(os.devnull, "wb") as output:
        subprocess.Popen([command, path], stdout=output, stderr=output,
                         close_fds=True)


def desktop_font(root, monospaced=False):
    try:
        import tkFont as font
    except ImportError:
        from tkinter import font
    available = set(font.families(root))
    if monospaced:
        candidates = ("Consolas", "Menlo", "DejaVu Sans Mono")
        fallback = "TkFixedFont"
    else:
        candidates = ("Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC",
                      "WenQuanYi Micro Hei", "DejaVu Sans")
        fallback = "TkDefaultFont"
    family = next((name for name in candidates if name in available), None)
    if family is None:
        family = root.tk.call("font", "actual", fallback, "-family")
    return (family, 11 if sys.platform == "darwin" else 9)
