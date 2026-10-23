#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : 图形界面启动与运行环境初始化
@ Author             : XCrane
"""
from __future__ import unicode_literals
import io
import json
import os
import sys
import traceback

try:
    text_type = unicode
except NameError:
    text_type = str

def _safe_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gb18030", "mbcs"):
            try:
                return value.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                pass
        return value.decode("utf-8", "replace")
    try:
        return text_type(value)
    except Exception:
        raw = repr(value)
        return raw if isinstance(raw, text_type) else raw.decode("ascii", "replace")

def _configure_runtime():
    roots = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(bundle)
        if bundle not in sys.path:
            sys.path.insert(0, bundle)
        os.environ["PATH"] = bundle + os.pathsep + os.environ.get("PATH", "")
    roots.append(sys.prefix)
    tcl_found = None
    tk_found = None
    for root in roots:
        tcl_candidates = [
            os.path.join(root, "tcl", "tcl8.5"),
            os.path.join(root, "Library", "lib", "tcl8.5"),
            os.path.join(root, "_MEI", "tcl", "tcl8.5"),
            os.path.join(root, "tcl"),
        ]
        tk_candidates = [
            os.path.join(root, "tcl", "tk8.5"),
            os.path.join(root, "Library", "lib", "tk8.5"),
            os.path.join(root, "_MEI", "tcl", "tk8.5"),
            os.path.join(root, "tk"),
        ]
        if tcl_found is None:
            for candidate in tcl_candidates:
                if os.path.isfile(os.path.join(candidate, "init.tcl")):
                    tcl_found = candidate
                    break
        if tk_found is None:
            for candidate in tk_candidates:
                if os.path.isfile(os.path.join(candidate, "tk.tcl")):
                    tk_found = candidate
                    break
    if tcl_found is not None:
        os.environ["TCL_LIBRARY"] = tcl_found
    if tk_found is not None:
        os.environ["TK_LIBRARY"] = tk_found

def _show_fatal(message):
    message = _safe_text(message)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "NAO 机器人验修工具箱", 0x10)
    except Exception:
        try:
            if sys.version_info[0] < 3:
                sys.stderr.write((message + "\n").encode("utf-8", "replace"))
            else:
                sys.stderr.write(message + "\n")
        except Exception:
            pass

def _write_fatal_log(details):
    try:
        details = _safe_text(details)
        from nao_diag.desktop import log_directory
        directory = log_directory()
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = os.path.join(directory, "gui_error.log")
        with open(path, "ab") as handle:
            handle.write((details + "\r\n").encode("utf-8", "replace"))
    except Exception:
        pass

def _check_runtime(output_path):
    result = {"ok": False, "frozen": bool(getattr(sys, "frozen", False))}
    root = None
    try:
        import naoqi
        import qi
        from nao_diag import __version__
        from nao_diag.config import load_config
        from nao_diag.gui import NaoToolboxApp, PROFILE_LABELS, tk
        if not callable(naoqi.ALProxy) or not callable(qi.Session):
            raise RuntimeError("NAOqi SDK 接口不可用")
        load_config()
        root = tk.Tk()
        root.withdraw()
        app = NaoToolboxApp(root)
        root.update_idletasks()
        result.update({
            "ok": True,
            "version": __version__,
            "python": sys.version,
            "sdk": _safe_text(naoqi.__file__),
            "tk": _safe_text(root.tk.call("info", "patchlevel")),
            "default_profile": app._profile(),
            "profiles": PROFILE_LABELS,
            "robot_id": app.robot_id_var.get(),
        })
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if root is not None:
            root.destroy()
    with io.open(output_path, "w", encoding="utf-8") as handle:
        handle.write(_safe_text(json.dumps(result, ensure_ascii=False, indent=2)))
    return 0 if result["ok"] else 3


def main():
    _configure_runtime()
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--check-runtime":
            return _check_runtime(sys.argv[2])
        from nao_diag.gui import main as gui_main
        return gui_main()
    except Exception as exc:
        message = "界面启动失败：%s" % _safe_text(exc)
        _write_fatal_log(traceback.format_exc())
        _show_fatal(message)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
