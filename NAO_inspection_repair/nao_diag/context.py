# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import io
import json
import os
import threading
from .compat import (console_write, ensure_dir, json_safe, now_iso, prompt_line,
                     to_text, write_text)
from .voice import SpeechAnnouncer

class RunLogger(object):
    def __init__(self, path, verbose=False):
        self.path = path
        self.verbose = bool(verbose)
        ensure_dir(os.path.dirname(os.path.abspath(path)))
        self._lock = threading.Lock()

    def _write(self, level, message, show=True):
        line = "%s [%s] %s" % (now_iso(), level, to_text(message))
        with self._lock:
            with io.open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if show:
            console_write(line)

    def info(self, message):
        self._write("INFO", message, True)

    def warning(self, message):
        self._write("WARN", message, True)

    def error(self, message):
        self._write("ERROR", message, True)

    def debug(self, message):
        self._write("DEBUG", message, self.verbose)

class DiagnosticContext(object):
    def __init__(self, client, robot, config, output_dir, options):
        self.client = client
        self.robot = robot
        self.config = config
        self.output_dir = ensure_dir(output_dir)
        self.artifact_dir = ensure_dir(os.path.join(output_dir, "artifacts"))
        self.log_dir = ensure_dir(os.path.join(output_dir, "robot_logs"))
        self.options = options
        self.results = []
        self.runtime = {}
        self.logger = RunLogger(
            os.path.join(output_dir, "run.log"),
            verbose=bool(getattr(options, "verbose", False)),
        )
        self.announcer = SpeechAnnouncer(
            client,
            enabled=bool(getattr(options, "voice", True)),
            requested_language=getattr(options, "language", "auto"),
            logger=self.logger,
        )

    @property
    def interactive(self):
        return bool(getattr(self.options, "interactive", False))

    @property
    def assume_yes(self):
        return bool(getattr(self.options, "assume_yes", False))

    def artifact_path(self, filename):
        return os.path.join(self.artifact_dir, filename)

    def relative_path(self, path):
        return os.path.relpath(path, self.output_dir).replace("\\", "/")

    def write_json_artifact(self, filename, value):
        path = self.artifact_path(filename)
        payload = json.dumps(json_safe(value), ensure_ascii=False, indent=2, sort_keys=True)
        write_text(path, payload + "\n")
        return self.relative_path(path)

    def write_text_artifact(self, filename, value):
        path = self.artifact_path(filename)
        write_text(path, value)
        return self.relative_path(path)

    def ask_yes_no(self, question, default=None):
        if not self.interactive:
            return default
        suffix = " [y/n] "
        while True:
            answer = prompt_line(to_text(question) + suffix).strip().lower()
            if answer in ("y", "yes", "是", "通过", "1"):
                return True
            if answer in ("n", "no", "否", "失败", "0"):
                return False
            if not answer and default is not None:
                return bool(default)
            console_write("请输入 y 或 n")

    def wait_enter(self, message):
        if self.assume_yes or not self.interactive:
            return
        prompt_line(to_text(message) + " [按 Enter 继续] ")

    def require_token(self, message, token):
        if self.assume_yes:
            self.logger.warning("已使用 -AssumeYes 跳过安全口令：%s" % token)
            return True
        if not self.interactive:
            return False
        answer = prompt_line("%s\n请输入 %s 继续：" % (to_text(message), to_text(token)))
        return answer.strip().upper() == to_text(token).upper()

