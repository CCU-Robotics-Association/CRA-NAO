# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import io
import json
import os
import shutil
import struct
import tempfile
import unittest
from nao_diag.client import NaoClient, normalize_battery_percent, pairs_to_dict
from nao_diag.compat import PY2, read_text
from nao_diag.config import DEFAULT_CONFIG, deep_merge, load_config
from nao_diag.context import DiagnosticContext
from nao_diag.log_analysis import analyze_paths, classify_line
from nao_diag.model import FAIL, PASS, SKIP, WARN, make_result, overall_status
from nao_diag.report import build_report_payload, write_reports
from nao_diag.tests_common import rgb_statistics, write_rgb_bmp
from nao_diag.tests_guided import (TOUCH_TEST_SENSORS, _sensor_key,
                                   _wait_sensor_cycle)

class Options(object):
    profile = "quick"
    verbose = False
    voice = False
    language = "auto"
    interactive = False
    assume_yes = False
    allow_motion = False
    allow_walk = False

class TouchClient(object):
    def __init__(self, sequences):
        self.sequences = dict((key, list(values))
                              for key, values in sequences.items())
        self.last = {}

    def memory_value(self, key, default=None):
        values = self.sequences.get(key)
        if values:
            value = values.pop(0)
            self.last[key] = value
            return value
        return self.last.get(key, default)

class TouchContext(object):
    def __init__(self, sequences):
        self.client = TouchClient(sequences)

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nao_diag_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_config_deep_merge_keeps_unmodified_defaults(self):
        merged = deep_merge(DEFAULT_CONFIG, {"thresholds": {"camera_stddev_min": 9.0}})
        self.assertEqual(merged["thresholds"]["camera_stddev_min"], 9.0)
        self.assertIn("joint_temperature_fail_c", merged["thresholds"])
        self.assertNotEqual(DEFAULT_CONFIG["thresholds"]["camera_stddev_min"], 9.0)

    def test_battery_normalization(self):
        self.assertEqual(normalize_battery_percent(0.5), 50.0)
        self.assertEqual(normalize_battery_percent(83), 83.0)
        self.assertIsNone(normalize_battery_percent("not-a-number"))

    def test_touch_uses_four_logical_operator_steps(self):
        self.assertEqual(TOUCH_TEST_SENSORS, (
            "Head/Touch", "LHand/Touch", "RHand/Touch", "ChestBoard/Button"))

    def test_whole_head_touch_accepts_any_one_pad(self):
        sequences = {
            _sensor_key("Head/Touch/Middle"): [0.0, 1.0, 0.0],
        }
        row = _wait_sensor_cycle(TouchContext(sequences), "Head/Touch", 0.5)
        self.assertEqual(row["status"], "passed")
        self.assertIn("Head/Touch/Middle", row["activated_members"])
        self.assertEqual(set(row["missing_members"]), {
            "Head/Touch/Front", "Head/Touch/Rear"})

    def test_naoqi_pair_map(self):
        self.assertEqual(pairs_to_dict([["severity", "warning"], ["id", 3]])["id"], 3)
        self.assertEqual(pairs_to_dict([1, 2]), [1, 2])

    def test_overall_status(self):
        results = [make_result("a", "A", PASS, "ok"),
                   make_result("b", "B", WARN, "check")]
        self.assertEqual(overall_status(results), WARN)
        results.append(make_result("c", "C", FAIL, "bad"))
        self.assertEqual(overall_status(results), FAIL)

    def test_log_classifier_prioritizes_critical(self):
        self.assertEqual(classify_line("motor SERIOUS temperature diagnosis")[0], "critical")
        self.assertEqual(classify_line("CameraTop failed to get image")[0], "error")
        self.assertEqual(classify_line("errors: 0")[0], None)

    def test_log_analysis_records_evidence(self):
        path = os.path.join(self.temp_dir, "naoqi.log")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write("normal line\nWarning 720 motor is too hot\nCamera failed\n")
        result = analyze_paths([path], max_samples=5)
        self.assertEqual(result["files_scanned"], 1)
        self.assertGreaterEqual(result["counts"]["critical"], 1)
        self.assertGreaterEqual(result["counts"]["error"], 1)

    def test_rgb_stats_and_bmp(self):
        data = bytearray([10, 20, 30, 100, 110, 120, 200, 210, 220, 50, 60, 70])
        stats = rgb_statistics(data, pixel_stride=1)
        self.assertEqual(stats["sample_pixels"], 4)
        self.assertGreater(stats["stddev"], 1.0)
        path = os.path.join(self.temp_dir, "frame.bmp")
        write_rgb_bmp(path, 2, 2, data)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(2), b"BM")
        self.assertGreater(os.path.getsize(path), 54)

    def test_report_writes_json_csv_and_html(self):
        options = Options()
        robot = {"robot_id": "测试-01", "ip": "192.0.2.1", "port": 9559}
        context = DiagnosticContext(
            NaoClient(robot["ip"]), robot, load_config(), self.temp_dir, options)
        context.results = [make_result(
            "camera", "相机", PASS, "有效", metrics={"mean": 100.5},
            artifacts=["artifacts/camera.bmp"])]
        payload = build_report_payload(context, "2026-01-01T00:00:00", "2026-01-01T00:00:01")
        paths = write_reports(context, payload)
        for path in paths.values():
            self.assertTrue(os.path.isfile(path))
        with open(paths["tests_csv"], "rb") as handle:
            self.assertEqual(handle.read(3), b"\xef\xbb\xbf")
        loaded = json.loads(read_text(paths["json"]))
        self.assertEqual(loaded["overall_status"], PASS)
        self.assertIn("NAO 机器人验修报告", read_text(paths["html"]))

    def test_context_json_artifact_preserves_unicode(self):
        options = Options()
        robot = {"robot_id": "中文编号", "ip": "192.0.2.1", "port": 9559}
        context = DiagnosticContext(
            NaoClient(robot["ip"]), robot, load_config(), self.temp_dir, options)
        utf8_bytes = "SDK中文消息".encode("utf-8")
        relative = context.write_json_artifact(
            "中文证据.json", {"robot_id": "中文编号", "sdk_message": utf8_bytes})
        loaded = json.loads(read_text(os.path.join(self.temp_dir, relative)))
        self.assertEqual(loaded["robot_id"], "中文编号")
        self.assertEqual(loaded["sdk_message"], "SDK中文消息")

    @unittest.skipUnless(PY2, "legacy pynaoqi boundary is Python 2 specific")
    def test_naoqi_proxy_encodes_unicode_arguments_on_python2(self):
        calls = []

        class RawProxy(object):
            def __init__(self):
                self.post = self

            def echo(self, *args, **kwargs):
                calls.append((args, kwargs))
                return True

        def factory(service, ip, port):
            self.assertIsInstance(service, str)
            self.assertNotIsInstance(service, unicode)  # noqa: F821
            self.assertIsInstance(ip, str)
            return RawProxy()

        proxy = NaoClient("127.0.0.1", proxy_factory=factory).proxy("ALMemory")
        proxy.post.echo("中文", ["one", "two"], {"key": "value"})
        args, kwargs = calls[0]
        self.assertTrue(all(isinstance(item, str) for item in args[1]))
        self.assertTrue(all(isinstance(item, str) for item in args[2].keys()))
        self.assertTrue(all(isinstance(item, str) for item in args[2].values()))
        self.assertEqual(kwargs, {})

if __name__ == "__main__":
    unittest.main()
