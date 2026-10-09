# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import time
from .compat import now_iso, to_text

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"
ERROR = "ERROR"

STATUS_RANK = {
    PASS: 0,
    SKIP: 1,
    WARN: 2,
    FAIL: 3,
    ERROR: 4,
}

def make_result(test_id, label, status, summary, metrics=None, details=None,
                started_at=None, duration_ms=None, artifacts=None):
    return {
        "id": to_text(test_id),
        "label": to_text(label),
        "status": status,
        "summary": to_text(summary),
        "metrics": metrics or {},
        "details": details or [],
        "artifacts": artifacts or [],
        "started_at": started_at or now_iso(),
        "duration_ms": int(duration_ms or 0),
    }

def skipped(test_id, label, summary):
    return make_result(test_id, label, SKIP, summary)

def overall_status(results):
    considered = [item.get("status", ERROR) for item in results]
    if not considered:
        return SKIP
    return max(considered, key=lambda item: STATUS_RANK.get(item, 99))

class Stopwatch(object):
    def __init__(self):
        self.started_at = now_iso()
        self._start = time.time()

    def elapsed_ms(self):
        return int(round((time.time() - self._start) * 1000.0))
