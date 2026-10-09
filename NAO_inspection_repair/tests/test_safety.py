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
import tempfile
import time
import unittest
from nao_diag.config import load_config
from nao_diag.model import FAIL, PASS, SKIP, WARN, make_result
from nao_diag.tests_auto import (test_battery as run_battery_test,
                                 test_diagnosis as run_diagnosis_test)
from nao_diag.tests_guided import _wait_sensor_cycle
from nao_diag.tests_motion import (SafetyAbort, _balance_limits,
                                   _capture_fall_event_baseline,
                                   _diagnosis_result_issues,
                                   _diagnosis_value_issues,
                                   _enable_walk_protections, _guard_fall_events,
                                   _fresh_motion_gate, _guard_joint_temperature,
                                   _motion_preflight,
                                   _pause_autonomous_life, _run_wakeup_task,
                                   _safe_robot_position, _test_one_joint,
                                   _validate_balance_sample,
                                   _verify_motion_protections,
                                   test_walk as run_walk_test)
from nao_diag.tests_motion import _explicit_non_motion_diagnosis
from nao_diag.compat import timestamp_slug

class Object(object):
    pass

class BatteryProxy(object):
    def getBatteryCharge(self):
        return 80

    def getBatteryStatus(self):
        return 128

class BatteryClient(object):
    def try_proxy(self, name):
        return (BatteryProxy(), None) if name == "ALBattery" else (None, "missing")

    def memory_values(self, keys):
        values = dict((key, 0) for key in keys)
        values["Device/SubDeviceList/Battery/Charge/Sensor/Status"] = 128
        return values

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nao_safety_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _context(self):
        ctx = Object()
        ctx.config = load_config()
        ctx.runtime = {"battery_percent": 80.0, "fsr_data_valid": True}
        ctx.results = [
            make_result("battery", "battery", PASS, "ok"),
            make_result("temperature", "temperature", PASS, "ok"),
            make_result("diagnosis", "diagnosis", PASS, "ok"),
            make_result("joints_static", "joints_static", PASS, "ok"),
            make_result("joints_motion", "joints_motion", PASS, "ok"),
            make_result("imu", "imu", PASS, "ok"),
            make_result("fsr", "fsr", WARN, "valid but unloaded"),
        ]
        return ctx

    def test_walk_preflight_is_fail_closed(self):
        ctx = self._context()
        self.assertEqual(_motion_preflight(ctx, walking=True), [])
        ctx.results = [item for item in ctx.results if item["id"] != "imu"]
        self.assertTrue(any("IMU" in item for item in _motion_preflight(ctx, walking=True)))
        ctx = self._context()
        for item in ctx.results:
            if item["id"] == "joints_motion":
                item["status"] = "FAIL"
        self.assertTrue(any("主动关节" in item for item in _motion_preflight(ctx, walking=True)))

    def test_joint_motion_preflight_requires_static_test(self):
        ctx = self._context()
        ctx.results = [item for item in ctx.results if item["id"] != "joints_static"]
        self.assertTrue(any("静态关节" in item for item in _motion_preflight(ctx)))

    def test_motion_preflight_requires_battery_test_pass(self):
        ctx = self._context()
        for item in ctx.results:
            if item["id"] == "battery":
                item["status"] = "FAIL"
        self.assertTrue(any("电池检查" in item for item in _motion_preflight(ctx)))

    def test_camera_only_diagnosis_does_not_block_motion(self):
        ctx = self._context()
        camera_metrics = {
            "api": {
                "getDiagnosisStatus": [0, ["CameraTop"]],
                "getPassiveDiagnosis": [],
                "getActiveDiagnosis": [0, ["CameraTop"]],
            },
            "active_error_keys": {"Diagnosis/Active/CameraTop/Error": 1},
            "temperature_error_keys": {},
            "notifications": [],
        }
        for index, item in enumerate(ctx.results):
            if item["id"] == "diagnosis":
                ctx.results[index] = make_result(
                    "diagnosis", "diagnosis", FAIL, "camera failed",
                    metrics=camera_metrics)
        self.assertEqual(_motion_preflight(ctx), [])
        self.assertTrue(ctx.runtime.get("non_motion_diagnosis_ignored"))

    def test_motion_or_unknown_diagnosis_remains_fail_closed(self):
        ctx = self._context()
        for index, item in enumerate(ctx.results):
            if item["id"] == "diagnosis":
                ctx.results[index] = make_result(
                    "diagnosis", "diagnosis", FAIL, "joint failed",
                    metrics={
                        "api": {"getActiveDiagnosis": [1, ["HeadYaw"]]},
                        "active_error_keys": {
                            "Diagnosis/Active/HeadYaw/Error": 1,
                        },
                        "temperature_error_keys": {},
                        "notifications": [],
                    })
        self.assertTrue(any("HeadYaw" in item for item in _motion_preflight(ctx)))
        ctx = self._context()
        for index, item in enumerate(ctx.results):
            if item["id"] == "diagnosis":
                ctx.results[index] = make_result(
                    "diagnosis", "diagnosis", FAIL, "unknown", metrics={})
        self.assertTrue(_motion_preflight(ctx))

    def test_fresh_diagnosis_classifier_ignores_camera_only(self):
        blockers, ignored = _diagnosis_value_issues(
            "getActiveDiagnosis", [0, ["CameraTop"]])
        self.assertEqual(blockers, [])
        self.assertTrue(ignored)
        blockers, ignored = _diagnosis_value_issues(
            "getActiveDiagnosis", [1, ["HeadYaw"]])
        self.assertTrue(blockers)
        self.assertEqual(ignored, [])
        self.assertTrue(_explicit_non_motion_diagnosis(
            "Diagnosis/Temperature/CameraTop/Error"))
        self.assertFalse(_explicit_non_motion_diagnosis(
            "UnknownProtectionEnabled"))
        self.assertFalse(_explicit_non_motion_diagnosis("CameraTop motor"))
        self.assertFalse(_explicit_non_motion_diagnosis(
            "Diagnosis/Active/LShoulderPitch/Error"))
        self.assertTrue(_explicit_non_motion_diagnosis("AudioBoard"))
        self.assertFalse(_explicit_non_motion_diagnosis("UnknownBoard"))

    def test_camera_notification_cannot_hide_motion_evidence(self):
        base_metrics = {
            "api": {
                "getDiagnosisStatus": [0, []],
                "getPassiveDiagnosis": [],
                "getActiveDiagnosis": [0, []],
            },
            "active_error_keys": {},
            "temperature_error_keys": {},
        }
        metrics = dict(base_metrics)
        metrics["notifications"] = [{
            "severity": "error", "device": "CameraTop",
            "message": "motor/DCM failure on HeadYaw",
        }]
        blockers, ignored = _diagnosis_result_issues(make_result(
            "diagnosis", "diagnosis", FAIL, "mixed", metrics=metrics))
        self.assertTrue(blockers)
        self.assertEqual(ignored, [])

        metrics = dict(base_metrics)
        metrics["notifications"] = [{
            "severity": "error", "device": "CameraTop",
            "message": "LHand failure",
        }]
        blockers, ignored = _diagnosis_result_issues(make_result(
            "diagnosis", "diagnosis", FAIL, "mixed hand", metrics=metrics))
        self.assertTrue(blockers)
        self.assertEqual(ignored, [])

        self.assertTrue(_explicit_non_motion_diagnosis("LHandTouch"))

        metrics = dict(base_metrics)
        metrics["notifications"] = [{
            "severity": "error", "device": "CameraTop",
            "message": "device did not return an image",
        }]
        blockers, ignored = _diagnosis_result_issues(make_result(
            "diagnosis", "diagnosis", FAIL, "camera", metrics=metrics))
        self.assertEqual(blockers, [])
        self.assertTrue(ignored)

    def test_diagnosis_summary_deduplicates_same_device_evidence(self):
        class Diagnosis(object):
            def getDiagnosisStatus(self): return [0, ["CameraTop"]]
            def getPassiveDiagnosis(self): return []
            def getActiveDiagnosis(self): return [0, ["CameraTop"]]

        class Client(object):
            def try_proxy(self, name):
                if name == "ALDiagnosis":
                    return Diagnosis(), None
                return None, "missing"
            def data_keys(self, prefix):
                if prefix == "Diagnosis/Active":
                    return ["Diagnosis/Active/CameraTop/Error"]
                return []
            def memory_values(self, keys):
                return dict((key, 1) for key in keys)
        ctx = Object()
        ctx.client = Client()
        written = {}
        def write_artifact(filename, value):
            written.update(value)
            return filename
        ctx.write_json_artifact = write_artifact
        result = run_diagnosis_test(ctx)
        self.assertEqual(result["status"], FAIL)
        self.assertIn("1 个诊断故障对象", result["summary"])
        self.assertEqual(result["metrics"]["fault_subjects"], ["CameraTop"])
        self.assertEqual(result["metrics"]["fault_evidence_count"], 3)
        self.assertEqual(written["fault_subjects"], ["CameraTop"])
        self.assertEqual(written["fault_evidence_count"], 3)

    def test_fresh_motion_gate_allows_camera_but_blocks_joint_diagnosis(self):
        class Battery(object):
            def getBatteryCharge(self): return 80

        class Diagnosis(object):
            def __init__(self, device): self.device = device
            def getDiagnosisStatus(self): return [0, [self.device]]
            def getPassiveDiagnosis(self): return []
            def getActiveDiagnosis(self): return [0, [self.device]]

        class Memory(object):
            def getTimestamp(self, key): return [False, 100, 1]

        class Client(object):
            def __init__(self, device):
                self.device = device
                self.memory = Memory()
            def try_proxy(self, name):
                if name == "ALBattery": return Battery(), None
                if name == "ALDiagnosis": return Diagnosis(self.device), None
                return None, "missing"
            def proxy(self, name):
                if name == "ALMemory": return self.memory
                raise RuntimeError("missing proxy")
            def data_keys(self, prefix):
                if prefix == "Diagnosis/Active":
                    return ["Diagnosis/Active/%s/Error" % self.device]
                return []
            def memory_values(self, keys):
                values = {}
                for key in keys:
                    if key.endswith("Battery/Temperature/Sensor/Status"):
                        values[key] = 0
                    elif key.startswith("Diagnosis/Active/Battery"):
                        values[key] = 0
                    elif key.startswith("Diagnosis/Temperature/Battery"):
                        values[key] = 0
                    elif key == "Diagnosis/Active/%s/Error" % self.device:
                        values[key] = 1
                    elif key.endswith("/Temperature/Sensor/Value"):
                        values[key] = 30.0
                    elif key.endswith("/Temperature/Sensor/Status"):
                        values[key] = 0
                    else:
                        values[key] = 80
                return values
            def memory_value(self, key, default=None):
                return True if key == "ALMotion/RobotIsStand" else default

        class Motion(object):
            def getBodyNames(self, name): return ["HeadYaw"]
            def getAngles(self, name, use_sensors): return [0.0]
            def moveIsActive(self): return False
            def areResourcesAvailable(self, names): return True

        ctx = self._context()
        ctx.client = Client("CameraTop")
        metrics = _fresh_motion_gate(ctx, Motion())
        self.assertTrue(metrics["diagnosis_ignored_non_motion"])
        ctx = self._context()
        ctx.client = Client("HeadYaw")
        with self.assertRaises(SafetyAbort):
            _fresh_motion_gate(ctx, Motion())

    def test_assume_yes_cannot_authorize_walk(self):
        ctx = Object()
        ctx.options = Object()
        ctx.options.allow_walk = True
        ctx.options.allow_motion = True
        ctx.assume_yes = True
        result = run_walk_test(ctx)
        self.assertEqual(result["status"], SKIP)
        self.assertIn("AssumeYes", result["summary"])

    def test_config_rejects_unsafe_motion_override(self):
        path = os.path.join(self.temp_dir, "unsafe.json")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(u'{"motion": {"joint_amplitude_rad": -10}}')
        with self.assertRaises(ValueError):
            load_config(path)

    def test_battery_charge_status_bitmask_is_not_a_failure(self):
        ctx = Object()
        ctx.client = BatteryClient()
        ctx.config = load_config()
        ctx.runtime = {}
        result = run_battery_test(ctx)
        self.assertEqual(result["status"], PASS)

    def test_chest_button_stuck_high_returns_immediately(self):
        client = Object()
        client.memory_value = lambda key, default=None: 1.0
        ctx = Object()
        ctx.client = client
        started = time.time()
        result = _wait_sensor_cycle(ctx, "ChestBoard/Button", 8.0)
        self.assertEqual(result["status"], "stuck_high")
        self.assertLess(time.time() - started, 0.5)

    def test_autonomous_life_must_confirm_disabled(self):
        class Life(object):
            def getState(self):
                return "solitary"

            def setState(self, state):
                pass

        ctx = Object()
        ctx.client = Object()
        ctx.client.try_proxy = lambda name: (Life(), None)
        with self.assertRaises(SafetyAbort):
            _pause_autonomous_life(ctx)

    def test_every_motion_protection_must_be_enabled(self):
        class Motion(object):
            def getFallManagerEnabled(self): return True
            def getCollisionProtectionEnabled(self, arm): return arm == "LArm"
            def getExternalCollisionProtectionEnabled(self, name): return True
            def getDiagnosisEffectEnabled(self): return True
        with self.assertRaises(SafetyAbort):
            _verify_motion_protections(Motion())

    def test_missing_temperature_blocks_joint(self):
        class Client(object):
            def memory_values(self, keys): return dict((key, None) for key in keys)
        ctx = Object()
        ctx.client = Client()
        ctx.config = load_config()
        with self.assertRaises(SafetyAbort):
            _guard_joint_temperature(ctx, "HeadYaw")

    def test_mass_based_balance_limits_and_strict_samples(self):
        ctx = self._context()

        class Motion(object):
            def getMass(self, name):
                return 5.4

        limits = _balance_limits(ctx, Motion())
        self.assertAlmostEqual(limits["standing_minimum_total_kg"], 3.24)
        self.assertAlmostEqual(limits["standing_maximum_total_kg"], 7.56)
        self.assertAlmostEqual(limits["standing_minimum_each_foot_kg"], 0.648)

        def sample(left, right):
            return {
                "angle_x": 0.0, "angle_y": 0.0, "robot_is_stand": True,
                "fsr_values": [left / 4.0] * 4 + [right / 4.0] * 4,
                "left_fsr_total": left, "right_fsr_total": right,
            }
        self.assertAlmostEqual(_validate_balance_sample(
            ctx, sample(2.7, 2.7), limits["standing_minimum_total_kg"],
            require_both_feet=True,
            maximum_total=limits["standing_maximum_total_kg"],
            minimum_each_foot=limits["standing_minimum_each_foot_kg"]), 5.4)
        for bad in (sample(1.6, 1.63), sample(3.8, 3.77), sample(0.64, 4.76)):
            with self.assertRaises(SafetyAbort):
                _validate_balance_sample(
                    ctx, bad, limits["standing_minimum_total_kg"],
                    require_both_feet=True,
                    maximum_total=limits["standing_maximum_total_kg"],
                    minimum_each_foot=limits["standing_minimum_each_foot_kg"])
        for bad_value in (float("nan"), float("inf")):
            bad = sample(2.7, 2.7)
            bad["fsr_values"][0] = bad_value
            with self.assertRaises(SafetyAbort):
                _validate_balance_sample(ctx, bad, 3.24)
        unsupported = sample(2.7, 2.7)
        unsupported["robot_is_stand"] = "unknown"
        with self.assertRaises(SafetyAbort):
            _validate_balance_sample(ctx, unsupported, 3.24, require_stand=True)

    def test_invalid_body_mass_blocks_balance_gate(self):
        ctx = self._context()

        class Motion(object):
            def __init__(self, value): self.value = value
            def getMass(self, name): return self.value

        for value in (None, float("nan"), float("inf"), 2.9, 8.1):
            with self.assertRaises(SafetyAbort):
                _balance_limits(ctx, Motion(value))

    def test_nonfinite_joint_limits_and_odometry_are_rejected(self):
        ctx = self._context()
        for limits in ([float("nan"), 1.0], [-1.0, float("inf")]):
            with self.assertRaises(SafetyAbort):
                _test_one_joint(ctx, Object(), "HeadYaw", limits, 0.0, 0.0)

        class Motion(object):
            def __init__(self, value): self.value = value
            def getRobotPosition(self, use_sensors): return self.value

        self.assertEqual(_safe_robot_position(Motion([1, 2, 3])), [1.0, 2.0, 3.0])
        for value in ([1, 2], [0, float("nan"), 0], [0, 0, float("inf")]):
            with self.assertRaises(SafetyAbort):
                _safe_robot_position(Motion(value))

    def test_wakeup_is_asynchronous_and_monitored(self):
        class Memory(object):
            def __init__(self):
                self.timestamps = {
                    "ALMotion/RobotIsFalling": [False, 10, 1],
                    "robotHasFallen": [False, 10, 2],
                }
            def getTimestamp(self, key):
                return list(self.timestamps[key])

        class Client(object):
            def __init__(self, memory): self.memory = memory
            def proxy(self, name): return self.memory
            def memory_values(self, keys):
                values = {}
                for key in keys:
                    if "/FSR/" in key:
                        values[key] = 0.675
                    elif "InertialSensor/Angle" in key:
                        values[key] = 0.0
                    elif key == "ALMotion/RobotIsStand":
                        values[key] = True
                    elif key.endswith("/Temperature/Sensor/Value"):
                        values[key] = 30.0
                    elif key.endswith("/Temperature/Sensor/Status"):
                        values[key] = 0
                    else:
                        values[key] = None
                return values

        class Logger(object):
            def __init__(self): self.errors = []
            def error(self, message): self.errors.append(message)

        class Post(object):
            def __init__(self, owner): self.owner = owner
            def wakeUp(self):
                self.owner.post_called += 1
                return 77

        class Motion(object):
            def __init__(self, keep_running=False):
                self.post = Post(self)
                self.post_called = 0
                self.checks = 0
                self.keep_running = keep_running
                self.killed = False
                self.stop_move_calls = 0
            def isRunning(self, task):
                if self.killed:
                    return False
                self.checks += 1
                return self.keep_running or self.checks == 1
            def killTask(self, task): self.killed = True
            def stopMove(self): self.stop_move_calls += 1
            def robotIsWakeUp(self): return True

        class Posture(object):
            def getPosture(self): return "StandInit"

        class Mass(object):
            def getMass(self, name): return 5.4

        ctx = self._context()
        memory = Memory()
        ctx.client = Client(memory)
        ctx.logger = Logger()
        ctx.runtime["fall_event_baseline"] = _capture_fall_event_baseline(ctx)
        fsr_keys = ["Device/SubDeviceList/%s/FSR/%s/Sensor/Value" % (foot, pos)
                    for foot in ("LFoot", "RFoot")
                    for pos in ("FrontLeft", "FrontRight", "RearLeft", "RearRight")]
        limits = _balance_limits(ctx, Mass())
        motion = Motion()
        result = _run_wakeup_task(
            ctx, motion, Posture(), ["HeadYaw"], fsr_keys, limits, timeout=1.0)
        self.assertEqual(result["task_id"], 77)
        self.assertEqual(result["actual_posture"], "StandInit")
        self.assertGreaterEqual(len(result["samples"]), 2)
        self.assertEqual(motion.post_called, 1)
        failing_motion = Motion(keep_running=True)
        memory.timestamps["ALMotion/RobotIsFalling"] = [True, 11, 1]
        with self.assertRaises(SafetyAbort):
            _run_wakeup_task(
                ctx, failing_motion, Posture(), ["HeadYaw"], fsr_keys,
                limits, timeout=1.0)
        self.assertTrue(failing_motion.killed)
        self.assertGreaterEqual(failing_motion.stop_move_calls, 1)

    def test_fall_events_use_timestamp_not_stale_true_value(self):
        class Memory(object):
            def __init__(self):
                self.values = {
                    "ALMotion/RobotIsFalling": [True, 20, 1],
                    "robotHasFallen": [True, 20, 2],
                }
            def getTimestamp(self, key): return list(self.values[key])

        class Client(object):
            def __init__(self): self.memory = Memory()
            def proxy(self, name): return self.memory

        ctx = self._context()
        ctx.client = Client()
        ctx.runtime["fall_event_baseline"] = _capture_fall_event_baseline(ctx)
        _guard_fall_events(ctx, "test")
        ctx.client.memory.values["ALMotion/RobotIsFalling"] = [True, 21, 1]
        with self.assertRaises(SafetyAbort):
            _guard_fall_events(ctx, "test")

    def test_walk_specific_protections_are_forced_on(self):
        class Motion(object):
            def __init__(self): self.config = None
            def setMotionConfig(self, config): self.config = config

        motion = Motion()
        result = _enable_walk_protections(motion)
        self.assertTrue(result["api_call_succeeded"])
        self.assertEqual(motion.config, [
            ["ENABLE_FOOT_CONTACT_PROTECTION", True],
            ["ENABLE_STIFFNESS_PROTECTION", True],
        ])

    def test_timestamp_slug_is_unique_in_tight_loop(self):
        values = [timestamp_slug() for _index in range(100)]
        self.assertEqual(len(values), len(set(values)))

if __name__ == "__main__":
    unittest.main()
