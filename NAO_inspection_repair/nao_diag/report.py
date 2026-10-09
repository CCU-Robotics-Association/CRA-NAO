# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import csv
import io
import json
import os    
from .compat import PY2, ensure_dir, json_safe, to_text, write_text
from .model import overall_status

STATUS_TEXT = {
    "PASS": "通过",
    "WARN": "警告",
    "FAIL": "失败",
    "SKIP": "未执行",
    "ERROR": "异常",
}

def _html(value):
    return (to_text(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))

def _json_text(value, indent=2):
    return to_text(json.dumps(json_safe(value), ensure_ascii=False, indent=indent, sort_keys=True))

def _csv_rows(path, rows):
    if PY2:
        handle = open(path, "wb")
        handle.write(b"\xef\xbb\xbf")
    else:
        handle = io.open(path, "w", encoding="utf-8-sig", newline="")
    try:
        writer = csv.writer(handle)
        for row in rows:
            if PY2:
                writer.writerow([to_text(item).encode("utf-8") for item in row])
            else:
                writer.writerow([to_text(item) for item in row])
    finally:
        handle.close()

def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key in sorted(value, key=lambda item: to_text(item)):
            child = "%s.%s" % (prefix, key) if prefix else to_text(key)
            for item in _flatten(value[key], child):
                yield item
    elif isinstance(value, (list, tuple)):
        for index, child_value in enumerate(value):
            child = "%s[%d]" % (prefix, index)
            for item in _flatten(child_value, child):
                yield item
    else:
        yield prefix, value

def verdict_for(status):
    if status in ("FAIL", "ERROR"):
        return "REJECT"
    if status in ("WARN", "SKIP"):
        return "ACCEPT_WITH_NOTES"
    return "ACCEPT"

def build_report_payload(context, started_at, finished_at):
    status = overall_status(context.results)
    return {
        "schema_version": "1.0",
        "tool_version": "1.0.0",
        "started_at": started_at,
        "finished_at": finished_at,
        "robot": context.robot,
        "overall_status": status,
        "verdict": verdict_for(status),
        "profile": getattr(context.options, "profile", "quick"),
        "safety": {
            "motion_authorized": bool(getattr(context.options, "allow_motion", False)),
            "walking_authorized": bool(getattr(context.options, "allow_walk", False)),
            "interactive": context.interactive,
            "manual_intervention_required": bool(
                context.runtime.get("motion_intervention_required", False)),
        },
        "voice": {
            "enabled": context.announcer.enabled,
            "language": context.announcer.language,
            "available_languages": context.announcer.available_languages,
            "last_error": context.announcer.error,
        },
        "config": context.config,
        "results": context.results,
    }

def write_reports(context, payload):
    output = context.output_dir
    ensure_dir(output)
    json_path = os.path.join(output, "report.json")
    write_text(json_path, _json_text(payload) + "\n")
    test_rows = [["test_id", "label", "status", "summary", "duration_ms", "artifacts"]]
    metric_rows = [["test_id", "metric_path", "value"]]
    for result in payload["results"]:
        test_rows.append([
            result.get("id"), result.get("label"), result.get("status"),
            result.get("summary"), result.get("duration_ms"),
            "; ".join(result.get("artifacts") or []),
        ])
        for path, value in _flatten(result.get("metrics", {})):
            metric_rows.append([result.get("id"), path, _json_text(value, indent=None)])
    _csv_rows(os.path.join(output, "tests.csv"), test_rows)
    _csv_rows(os.path.join(output, "metrics.csv"), metric_rows)
    html_path = os.path.join(output, "report.html")
    write_text(html_path, render_html(payload))
    return {"json": json_path, "html": html_path,
            "tests_csv": os.path.join(output, "tests.csv"),
            "metrics_csv": os.path.join(output, "metrics.csv")}

def render_html(payload):
    robot = payload.get("robot", {})
    rows = []
    for result in payload.get("results", []):
        artifacts = []
        for path in result.get("artifacts", []):
            escaped = _html(path)
            artifacts.append('<a href="%s">%s</a>' % (escaped, escaped))
        details = {
            "metrics": result.get("metrics", {}),
            "details": result.get("details", []),
        }
        rows.append("""
        <tr>
          <td><code>{id}</code><br><span class="muted">{label}</span></td>
          <td><span class="badge {status}">{status_text}</span></td>
          <td>{summary}<br>{artifacts}<details><summary>数据明细</summary><pre>{details}</pre></details></td>
          <td>{duration} ms</td>
        </tr>""".format(
            id=_html(result.get("id")), label=_html(result.get("label")),
            status=_html(result.get("status")),
            status_text=_html(STATUS_TEXT.get(result.get("status"), result.get("status"))),
            summary=_html(result.get("summary")), artifacts=" · ".join(artifacts),
            details=_html(_json_text(details)), duration=int(result.get("duration_ms", 0)),
        ))
    counts = {}
    for result in payload.get("results", []):
        status = result.get("status", "ERROR")
        counts[status] = counts.get(status, 0) + 1
    count_text = " · ".join("%s %d" % (STATUS_TEXT.get(key, key), counts.get(key, 0))
                            for key in ("PASS", "WARN", "FAIL", "SKIP", "ERROR")
                            if counts.get(key, 0))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NAO 验修报告 - {robot_id}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f4f6f8;color:#17212b}}
.wrap{{max-width:1180px;margin:32px auto;padding:0 20px}} .hero{{background:#fff;border-radius:14px;padding:24px;box-shadow:0 4px 18px #17212b14}}
h1{{margin:0 0 8px}} .muted{{color:#66788a;font-size:.9em}} .summary{{display:flex;gap:16px;flex-wrap:wrap;margin-top:18px}}
.card{{padding:12px 16px;border-radius:10px;background:#eef2f5}} table{{width:100%;border-collapse:collapse;background:#fff;margin-top:20px;border-radius:12px;overflow:hidden}}
th,td{{padding:13px 12px;border-bottom:1px solid #e7ebef;text-align:left;vertical-align:top}} th{{background:#eaf0f5}} code{{white-space:nowrap}}
.badge{{font-weight:700;padding:4px 9px;border-radius:999px}} .PASS{{background:#d9f7e7;color:#087443}} .WARN{{background:#fff1c7;color:#8a5b00}}
.FAIL,.ERROR{{background:#ffe0df;color:#a51d19}} .SKIP{{background:#e7ebef;color:#536273}} details{{margin-top:8px}} pre{{white-space:pre-wrap;max-height:500px;overflow:auto;background:#101820;color:#e8f0f5;padding:12px;border-radius:8px}}
a{{color:#0068b5}}
</style></head><body><div class="wrap"><section class="hero">
<h1>NAO 机器人验修报告</h1><div class="muted">编号 {robot_id} · {ip}:{port} · {started} 至 {finished}</div>
<div class="summary"><div class="card"><b>总体：{overall}</b><br>{verdict}</div><div class="card"><b>测试概况</b><br>{counts}</div><div class="card"><b>模式</b><br>{profile}</div></div>
</section><table><thead><tr><th>项目</th><th>结果</th><th>结论与数据</th><th>耗时</th></tr></thead><tbody>{rows}</tbody></table>
</div></body></html>""".format(
        robot_id=_html(robot.get("robot_id", "NAO")), ip=_html(robot.get("ip", "")),
        port=_html(robot.get("port", "")), started=_html(payload.get("started_at", "")),
        finished=_html(payload.get("finished_at", "")), overall=_html(STATUS_TEXT.get(payload.get("overall_status"), payload.get("overall_status"))),
        verdict=_html(payload.get("verdict")), counts=_html(count_text), profile=_html(payload.get("profile")), rows="".join(rows),
    )
