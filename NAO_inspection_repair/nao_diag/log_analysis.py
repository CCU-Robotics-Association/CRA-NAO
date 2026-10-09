# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import io
import os
import re
from .compat import filesystem_text, to_text

CRITICAL_PATTERNS = [
    ("crash", re.compile(r"\b(fatal|critical|segmentation fault|segfault|core dump)\b", re.I)),
    ("temperature", re.compile(r"\b(overheat|overheated|too hot|SERIOUS temperature|thermal shutdown)\b", re.I)),
    ("motion", re.compile(r"\b(cannot move anymore|emergency stop|robot has fallen)\b", re.I)),
]

ERROR_PATTERNS = [
    ("communication", re.compile(r"\b(disconnected|connection lost|communication failure|no ack)\b", re.I)),
    ("hardware", re.compile(r"\b(board|motor|sensor|camera|micro|sonar)\b.{0,50}\b(error|failed|failure|fault)\b", re.I)),
    ("generic", re.compile(r"\b(error|failed|failure|exception)\b", re.I)),
]

WARNING_PATTERNS = [
    ("warning", re.compile(r"\b(warn(?:ing)?|degraded|retry|timeout)\b", re.I)),
]

IGNORE_PATTERNS = [
    re.compile(r"\b(no|without)\s+(?:new\s+)?errors?\b", re.I),
    re.compile(r"errors?\s*[:=]\s*0\b", re.I),
    re.compile(r"only a warning, won'?t be logged", re.I),
    re.compile(r"getMethodHelp", re.I),
]

def classify_line(line):
    text = to_text(line).strip()
    if not text:
        return None, None
    if any(pattern.search(text) for pattern in IGNORE_PATTERNS):
        return None, None
    for category, pattern in CRITICAL_PATTERNS:
        if pattern.search(text):
            return "critical", category
    for category, pattern in ERROR_PATTERNS:
        if pattern.search(text):
            return "error", category
    for category, pattern in WARNING_PATTERNS:
        if pattern.search(text):
            return "warning", category
    return None, None

def analyze_paths(paths, max_samples=30):
    summary = {
        "files_scanned": 0,
        "lines_scanned": 0,
        "counts": {"critical": 0, "error": 0, "warning": 0},
        "categories": {},
        "samples": {"critical": [], "error": [], "warning": []},
        "unreadable_files": [],
    }
    for path in paths:
        path = filesystem_text(path)
        if not os.path.isfile(path):
            continue
        summary["files_scanned"] += 1
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, 1):
                    summary["lines_scanned"] += 1
                    severity, category = classify_line(line)
                    if not severity:
                        continue
                    summary["counts"][severity] += 1
                    summary["categories"][category] = summary["categories"].get(category, 0) + 1
                    bucket = summary["samples"][severity]
                    if len(bucket) < int(max_samples):
                        bucket.append({
                            "file": os.path.basename(path),
                            "line": line_number,
                            "category": category,
                            "text": to_text(line).strip()[:500],
                        })
        except Exception as exc:
            summary["unreadable_files"].append({
                "file": path,
                "error": to_text(exc),
            })
    return summary

def discover_log_files(root):
    paths = []
    root = filesystem_text(root)
    if not root or not os.path.isdir(root):
        return paths
    for current, _directories, filenames in os.walk(root):
        current = filesystem_text(current)
        for filename in filenames:
            filename = filesystem_text(filename)
            if filename.lower().endswith((".log", ".txt", ".journal")):
                paths.append(os.path.join(current, filename))
    return sorted(paths)
