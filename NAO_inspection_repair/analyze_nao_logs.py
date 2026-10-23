#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : 离线机器人日志分析
@ Author             : XCrane
"""
from __future__ import print_function, unicode_literals
import argparse
import json
import os
import sys
from nao_diag.compat import console_write, decode_argv, stream_write, write_text
from nao_diag.log_analysis import analyze_paths, discover_log_files

class UnicodeArgumentParser(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            stream_write(file or sys.stderr, message)

def main(argv=None):
    parser = UnicodeArgumentParser(description="离线扫描已有 NAO/NAOqi 日志")
    parser.add_argument("path", help="日志目录")
    parser.add_argument("--output", help="分析 JSON 输出路径")
    parser.add_argument("--max-samples", type=int, default=30)
    args = parser.parse_args(decode_argv(argv))
    if not os.path.isdir(args.path):
        parser.error("日志目录不存在：%s" % args.path)
    if args.max_samples < 1:
        parser.error("--max-samples 必须大于 0")
    paths = discover_log_files(args.path)
    if not paths:
        console_write("目录内没有可分析的日志文件")
        return 1
    result = analyze_paths(paths, max_samples=args.max_samples)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        write_text(args.output, payload + "\n")
        console_write("分析结果已保存：%s" % os.path.abspath(args.output))
    else:
        console_write(payload)
    counts = result["counts"]
    if counts["critical"]:
        return 2
    if counts["error"] or counts["warning"] or result["unreadable_files"]:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
