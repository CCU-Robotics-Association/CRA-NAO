# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import print_function, unicode_literals
import datetime
import io
import math
import os
import re
import sys
import threading

PY2 = sys.version_info[0] == 2
if PY2:
    text_type = unicode  # noqa: F821
    binary_type = str
else:
    text_type = str
    binary_type = bytes

_TIMESTAMP_LOCK = threading.Lock()
_TIMESTAMP_SEQUENCE = 0

def to_text(value, encoding="utf-8"):
    if value is None:
        return ""
    if isinstance(value, text_type):
        return value
    if isinstance(value, binary_type):
        return value.decode(encoding, "replace")
    try:
        return text_type(value)
    except Exception:
        return repr(value)

def filesystem_text(value):
    encoding = sys.getfilesystemencoding() or ("mbcs" if os.name == "nt" else "utf-8")
    return to_text(value, encoding)

def decode_argv(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if PY2:
        return [filesystem_text(item) for item in values]
    return values

def stream_write(stream, value, end=""):
    message = to_text(value) + to_text(end)
    if PY2:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        try:
            stream.write(message.encode(encoding, "replace"))
        except Exception:
            stream.write(message.encode("utf-8", "replace"))
    else:
        stream.write(message)
    stream.flush()

def console_write(value, end="\n"):
    stream_write(sys.stdout, value, end=end)

def prompt_line(prompt):
    console_write(prompt, end="")
    if PY2:
        raw = raw_input()  # noqa: F821
        encoding = getattr(sys.stdin, "encoding", None) or "utf-8"
        return to_text(raw, encoding).strip()
    return input().strip()

def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()

def timestamp_slug():
    global _TIMESTAMP_SEQUENCE
    value = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    with _TIMESTAMP_LOCK:
        _TIMESTAMP_SEQUENCE += 1
        sequence = _TIMESTAMP_SEQUENCE
    return "%s_%d_%03d" % (value, os.getpid(), sequence)

def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path

def write_text(path, value):
    parent = os.path.dirname(os.path.abspath(path))
    ensure_dir(parent)
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(to_text(value))

def read_text(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()

def json_safe(value):
    if isinstance(value, binary_type):
        return value.decode("utf-8", "replace")
    if isinstance(value, text_type):
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            safe_key = json_safe(key)
            if not isinstance(safe_key, text_type):
                safe_key = to_text(safe_key)
            result[safe_key] = json_safe(item)
        return result
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value, key=lambda item: to_text(item))]
    return value

def safe_float(value, default=None):
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError, OverflowError):
        return default

def is_finite(value):
    return safe_float(value, None) is not None

def slugify(value, fallback="nao"):
    value = to_text(value).strip()
    value = re.compile(r"[^\w.-]+", re.UNICODE).sub("_", value)
    value = value.strip("._-")
    value = value[:80]
    if value.upper() in ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3",
                         "LPT1", "LPT2", "LPT3"):
        value = "_" + value
    return value or fallback

def mean(values):
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / float(len(values))

def stddev(values):
    values = list(values)
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((item - avg) ** 2 for item in values) / float(len(values)))
