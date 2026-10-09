# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
from .compat import to_text

class SpeechAnnouncer(object):
    def __init__(self, client, enabled=True, requested_language="auto", logger=None):
        self.client = client
        self.enabled = bool(enabled)
        self.requested_language = to_text(requested_language or "auto")
        self.logger = logger
        self.proxy = None
        self.language = None
        self.original_language = None
        self.available_languages = []
        self.error = None
        if self.enabled:
            self._initialize()

    def _log(self, message):
        if self.logger:
            self.logger.debug(message)

    def _initialize(self):
        try:
            self.proxy = self.client.proxy("ALTextToSpeech")
            try:
                self.original_language = to_text(self.proxy.getLanguage())
            except Exception:
                self.original_language = None
            try:
                self.available_languages = list(self.proxy.getAvailableLanguages())
            except Exception:
                self.available_languages = []
            self.language = self._select_language()
            if self.language:
                try:
                    self.proxy.setLanguage(self.language)
                except Exception as exc:
                    self._log("无法切换 TTS 语言：%s" % to_text(exc))
        except Exception as exc:
            self.error = to_text(exc)
            self.proxy = None

    def _select_language(self):
        available = dict((to_text(item).lower(), to_text(item))
                         for item in self.available_languages)
        requested = self.requested_language.lower()
        if requested != "auto" and requested in available:
            return available[requested]
        for candidate in ("chinese", "mandarin", "english"):
            if candidate in available:
                return available[candidate]
        if self.available_languages:
            return to_text(self.available_languages[0])
        return None

    @property
    def is_chinese(self):
        language = to_text(self.language).lower()
        return language in ("chinese", "mandarin")

    def say(self, chinese, english=None, asynchronous=False):
        if not self.enabled or self.proxy is None:
            return False
        phrase = to_text(chinese if self.is_chinese or not english else english)
        payload = phrase.encode("utf-8")
        try:
            if asynchronous:
                self.proxy.post.say(payload)
            else:
                self.proxy.say(payload)
            return True
        except Exception as exc:
            self.error = to_text(exc)
            self._log("TTS 播报失败：%s" % self.error)
            return False

    def test_passed(self, label):
        return self.say(
            "%s，检查通过" % to_text(label),
            "%s passed." % to_text(label),
        )

    def final(self, overall, robot_id):
        robot_id = to_text(robot_id)
        if overall == "PASS":
            return self.say(
                "%s，全部已执行项目检查通过" % robot_id,
                "%s: all executed checks passed." % robot_id,
            )
        if overall in ("FAIL", "ERROR"):
            return self.say(
                "%s，检查完成，发现故障，请查看报告" % robot_id,
                "%s: checks finished; faults were found. Review the report." % robot_id,
            )
        return self.say(
            "%s，检查完成，有警告或未完成项目，请查看报告" % robot_id,
            "%s: checks finished with warnings or incomplete items." % robot_id,
        )

    def restore(self):
        if self.proxy is None or not self.original_language:
            return
        try:
            if to_text(self.original_language) != to_text(self.language):
                self.proxy.setLanguage(self.original_language)
        except Exception as exc:
            self.error = to_text(exc)
            self._log("无法恢复 TTS 语言：%s" % self.error)
