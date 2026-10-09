# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import re
import time
from .client import normalize_battery_percent
from .compat import safe_float, to_text
from .model import FAIL, PASS, SKIP, WARN, Stopwatch
from .tests_common import active_value, finish, temperature_snapshot

class SafetyAbort(RuntimeError):
    pass

_FALL_EVENT_CANDIDATES = (
    ("falling", ("ALMotion/RobotIsFalling", "robotIsFalling")),
    ("fallen", ("robotHasFallen",)),
)

def _timestamp_record(memory, key):
    raw = memory.getTimestamp(key)
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        raise SafetyAbort("跌倒事件 %s 的时间戳格式无效" % key)
    seconds = safe_float(raw[1], None)
    microseconds = safe_float(raw[2], None)
    if seconds is None or microseconds is None:
        raise SafetyAbort("跌倒事件 %s 的时间戳缺失" % key)
    return {"key": key, "value": raw[0],
            "timestamp": [int(seconds), int(microseconds)]}

def _capture_fall_event_baseline(ctx):
    try:
        memory = ctx.client.proxy("ALMemory")
    except Exception as exc:
        raise SafetyAbort("无法访问 ALMemory 以监控跌倒事件：%s" % to_text(exc))
    baseline = {}
    for label, candidates in _FALL_EVENT_CANDIDATES:
        errors = []
        for key in candidates:
            try:
                baseline[label] = _timestamp_record(memory, key)
                break
            except Exception as exc:
                errors.append("%s: %s" % (key, to_text(exc)))
        if label not in baseline:
            raise SafetyAbort("无法建立跌倒事件时间戳基线（%s）" % "; ".join(errors))
    return baseline

def _guard_fall_events(ctx, phase):
    baseline = ctx.runtime.get("fall_event_baseline")
    if not baseline:
        raise SafetyAbort("%s 前没有跌倒事件时间戳基线" % phase)
    try:
        memory = ctx.client.proxy("ALMemory")
    except Exception as exc:
        raise SafetyAbort("%s 期间无法访问 ALMemory：%s" % (phase, to_text(exc)))
    current = {}
    for label, original in baseline.items():
        try:
            current[label] = _timestamp_record(memory, original["key"])
        except Exception as exc:
            raise SafetyAbort("%s 期间无法读取跌倒事件时间戳：%s" %
                              (phase, to_text(exc)))
        if current[label]["timestamp"] != original["timestamp"]:
            raise SafetyAbort("%s 期间检测到新的跌倒事件 %s" %
                              (phase, original["key"]))
    return current

def _stand_supported(value):
    if isinstance(value, bool):
        return value
    number = safe_float(value, None)
    return number is not None and number >= 0.5

def _result_status(ctx, test_id):
    result = _result_entry(ctx, test_id)
    if result is not None:
        return result.get("status")
    return None

def _result_entry(ctx, test_id):
    for result in ctx.results:
        if result.get("id") == test_id:
            return result
    return None

_MOTION_DIAGNOSIS_TOKENS = (
    "motor", "joint", "actuator", "battery", "temperature", "overheat",
    "inertial", "imu", "fsr", "fall", "stiffness", "collision",
    "electricnetwork", "dcm",
)

_MOTION_JOINT_NAME_TOKENS = (
    "headyaw", "headpitch", "shoulderpitch", "shoulderroll", "elbowyaw",
    "elbowroll", "wristyaw", "hipyawpitch", "hiproll", "hippitch",
    "kneepitch", "anklepitch", "ankleroll",
)

def _diagnosis_identifier_subject(identifier):
    text = to_text(identifier).strip()
    parts = [part for part in text.split("/") if part]
    if len(parts) >= 4 and parts[0].lower() == "diagnosis" and parts[-1].lower() in (
            "error", "status"):
        return parts[-2]
    return text

def _contains_motion_diagnosis_evidence(identifier):
    text = to_text(identifier).strip().lower()
    if any(token in text for token in _MOTION_DIAGNOSIS_TOKENS):
        return True
    words = re.findall(r"[a-z0-9]+", text)
    if any(word in ("lhand", "rhand") for word in words):
        return True
    compact = re.sub(r"[^a-z0-9]+", "", text)
    return any(token in compact for token in _MOTION_JOINT_NAME_TOKENS)

def _explicit_non_motion_diagnosis(identifier):
    text = _diagnosis_identifier_subject(identifier).lower()
    if not text:
        return False
    if _contains_motion_diagnosis_evidence(text):
        return False
    compact = re.sub(r"[^a-z0-9]+", "", text)
    if any(token in compact for token in (
            "camera", "videodevice", "audiodevice", "microphone", "speaker",
            "sonar", "ultrasound")):
        return True
    if compact.startswith(("video", "vision", "audio")):
        return True
    if (compact.startswith(("touch", "tactile", "bumper")) or
            compact.endswith(("touch", "tactile", "bumper")) or
            "touchsensor" in compact):
        return True
    if compact in ("led", "leds") or compact.startswith("led"):
        return True
    return any(token in compact for token in (
        "faceled", "earled", "chestled", "feetled",
    ))

def _append_unique(target, values):
    for value in values:
        value = to_text(value)
        if value not in target:
            target.append(value)

def _diagnosis_value_issues(source, value):
    blockers = []
    ignored = []
    if value is None or value is False or value == 0 or value == "":
        return blockers, ignored
    if isinstance(value, (list, tuple)):
        if not value:
            return blockers, ignored
        if (len(value) == 2 and safe_float(value[0], None) is not None and
                isinstance(value[1], (list, tuple))):
            severity = safe_float(value[0], 0.0)
            devices = list(value[1])
            if devices:
                for device in devices:
                    label = "%s: %s" % (source, to_text(device))
                    if _explicit_non_motion_diagnosis(device):
                        ignored.append(label)
                    else:
                        blockers.append(label)
            elif severity > 0:
                blockers.append("%s: severity=%s（未提供故障设备）" %
                                (source, severity))
            return blockers, ignored
        if all(not isinstance(item, (list, tuple, dict)) for item in value):
            for item in value:
                label = "%s: %s" % (source, to_text(item))
                if _explicit_non_motion_diagnosis(item):
                    ignored.append(label)
                else:
                    blockers.append(label)
            return blockers, ignored
        blockers.append("%s: 无法分类的诊断结果 %s" % (source, to_text(value)))
        return blockers, ignored
    if isinstance(value, dict):
        blockers.append("%s: 无法分类的诊断结果 %s" % (source, to_text(value)))
    elif active_value(value):
        label = "%s: %s" % (source, to_text(value))
        if _explicit_non_motion_diagnosis(value):
            ignored.append(label)
        else:
            blockers.append(label)
    return blockers, ignored

def _diagnosis_result_issues(result):
    if result is None:
        return ["内置诊断未执行"], []
    status = result.get("status")
    if status == PASS:
        return [], []
    if status not in (FAIL, WARN):
        return ["内置诊断状态无法用于运动放行（%s）" % (status or "未知")], []
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return ["内置诊断缺少可分类数据（%s）" % status], []
    blockers = []
    ignored = []
    api = metrics.get("api", {})
    if not isinstance(api, dict):
        blockers.append("ALDiagnosis 返回结构无效")
    elif not api:
        blockers.append("ALDiagnosis 没有可用于运动放行的结果")
    else:
        for method, value in api.items():
            if to_text(method).endswith("_error"):
                blockers.append("%s: %s" % (method, to_text(value)))
                continue
            found_blockers, found_ignored = _diagnosis_value_issues(method, value)
            _append_unique(blockers, found_blockers)
            _append_unique(ignored, found_ignored)
    for bucket_name in ("active_error_keys", "temperature_error_keys"):
        values = metrics.get(bucket_name, {})
        if not isinstance(values, dict):
            blockers.append("%s 返回结构无效" % bucket_name)
            continue
        for key, value in values.items():
            if not active_value(value):
                continue
            label = "%s: %s" % (to_text(key), to_text(value))
            if _explicit_non_motion_diagnosis(key):
                _append_unique(ignored, [label])
            else:
                _append_unique(blockers, [label])
    notifications = metrics.get("notifications", [])
    if not isinstance(notifications, (list, tuple)):
        blockers.append("系统通知返回结构无效")
    else:
        for item in notifications:
            if isinstance(item, dict):
                severity = to_text(item.get("severity", "")).lower()
                if severity not in ("warning", "warn", "error", "critical", "fatal"):
                    continue
                device = item.get("device")
                supporting = [item.get("name"), item.get("id"), item.get("message")]
                supporting = [to_text(value) for value in supporting if value]
                if device:
                    identifier = " | ".join([to_text(device)] + supporting)
                    explicitly_non_motion = (
                        _explicit_non_motion_diagnosis(device) and
                        not _contains_motion_diagnosis_evidence(" | ".join(supporting)))
                else:
                    identifier = " | ".join(supporting) or to_text(item)
                    explicitly_non_motion = _explicit_non_motion_diagnosis(identifier)
            else:
                severity = "error"
                identifier = item
                explicitly_non_motion = _explicit_non_motion_diagnosis(identifier)
            label = "notification: %s" % to_text(identifier)
            if explicitly_non_motion:
                _append_unique(ignored, [label])
            else:
                _append_unique(blockers, [label])
    if not blockers and not ignored:
        blockers.append("内置诊断为 %s，但没有可确认的故障分类" % status)
    return blockers, ignored

def _motion_preflight(ctx, walking=False):
    reasons = []
    battery_status = _result_status(ctx, "battery")
    if battery_status != "PASS":
        reasons.append("电池检查未明确通过（%s）" % (battery_status or "未执行"))
    minimum_battery = float(ctx.config["thresholds"]["motion_min_battery_percent"])
    battery = ctx.runtime.get("battery_percent")
    if battery is None:
        reasons.append("没有有效电池读数")
    elif battery < minimum_battery:
        reasons.append("电量 %.1f%% 低于运动门槛 %.1f%%" % (battery, minimum_battery))
    temperature_status = _result_status(ctx, "temperature")
    if temperature_status not in ("PASS",):
        reasons.append("温度检查未明确通过（%s）" % (temperature_status or "未执行"))
    diagnosis_blockers, diagnosis_ignored = _diagnosis_result_issues(
        _result_entry(ctx, "diagnosis"))
    if diagnosis_blockers:
        reasons.append("运动相关内置诊断未通过：%s" %
                       "；".join(diagnosis_blockers[:4]))
    if diagnosis_ignored:
        ctx.runtime["non_motion_diagnosis_ignored"] = diagnosis_ignored
    static_status = _result_status(ctx, "joints_static")
    if static_status != "PASS":
        reasons.append("静态关节检查未明确通过（%s）" % (static_status or "未执行"))
    if walking:
        for test_id, label in (("joints_motion", "主动关节"),
                               ("imu", "IMU")):
            status = _result_status(ctx, test_id)
            if status != "PASS":
                reasons.append("%s 检查未明确通过（%s）" % (label, status or "未执行"))
        fsr_status = _result_status(ctx, "fsr")
        if fsr_status not in ("PASS", "WARN") or not ctx.runtime.get("fsr_data_valid"):
            reasons.append("FSR 数据完整性未明确通过（%s）" % (fsr_status or "未执行"))
    return reasons

def _diagnosis_value_has_fault(value):
    blockers, ignored = _diagnosis_value_issues("diagnosis", value)
    return bool(blockers or ignored)

def _fresh_motion_gate(ctx, motion, walking=False):
    thresholds = ctx.config["thresholds"]
    metrics = {}
    names = [to_text(name) for name in motion.getBodyNames("Body")]
    if not names:
        raise SafetyAbort("无法获取关节列表")
    sensor_angles = [safe_float(value, None) for value in motion.getAngles("Body", True)]
    if len(sensor_angles) != len(names) or any(value is None for value in sensor_angles):
        raise SafetyAbort("运动前关节传感角数据不完整")
    metrics["joint_sensor_count"] = len(sensor_angles)
    try:
        move_active = bool(motion.moveIsActive())
        resources_available = bool(motion.areResourcesAvailable(names))
    except Exception as exc:
        raise SafetyAbort("无法确认 ALMotion 运动资源为空闲：%s" % to_text(exc))
    metrics["move_is_active"] = move_active
    metrics["body_resources_available"] = resources_available
    if move_active:
        raise SafetyAbort("检测到已有行走任务，拒绝启动验收动作")
    if not resources_available:
        raise SafetyAbort("Body 运动资源正被其他任务占用")
    battery, _battery_error = ctx.client.try_proxy("ALBattery")
    raw_charge = None
    if battery is not None:
        try:
            raw_charge = battery.getBatteryCharge()
        except Exception:
            raw_charge = None
    battery_keys = [
        "Device/SubDeviceList/Battery/Charge/Sensor/Value",
        "Device/SubDeviceList/Battery/Temperature/Sensor/Status",
        "Diagnosis/Active/Battery/Error",
        "Diagnosis/Temperature/Battery/Error",
    ]
    battery_values = ctx.client.memory_values(battery_keys)
    percent = normalize_battery_percent(raw_charge)
    if percent is None:
        percent = normalize_battery_percent(battery_values.get(battery_keys[0]))
    metrics["battery_percent"] = percent
    metrics["battery_safety_values"] = battery_values
    minimum_battery = float(thresholds["motion_min_battery_percent"])
    if percent is None or percent < minimum_battery:
        raise SafetyAbort("最新电量缺失或低于运动门槛 %.1f%%" % minimum_battery)
    if battery_values.get(battery_keys[1]) is None:
        raise SafetyAbort("无法读取最新电池温度状态")
    if any(active_value(battery_values.get(key)) for key in battery_keys[1:]):
        raise SafetyAbort("最新电池温度/诊断状态异常")
    diagnosis, diagnosis_error = ctx.client.try_proxy("ALDiagnosis")
    if diagnosis is None:
        raise SafetyAbort("无法执行最新内置诊断：%s" % diagnosis_error)
    diagnosis_values = {}
    diagnosis_ignored = []
    for method in ("getDiagnosisStatus", "getPassiveDiagnosis", "getActiveDiagnosis"):
        try:
            value = getattr(diagnosis, method)()
        except Exception as exc:
            raise SafetyAbort("最新诊断 %s 调用失败：%s" % (method, to_text(exc)))
        diagnosis_values[method] = value
        blockers, ignored = _diagnosis_value_issues(method, value)
        if blockers:
            raise SafetyAbort("最新运动相关诊断故障：%s" % "；".join(blockers[:4]))
        _append_unique(diagnosis_ignored, ignored)
    metrics["diagnosis"] = diagnosis_values
    diagnosis_keys = []
    for prefix in ("Diagnosis/Active", "Diagnosis/Temperature"):
        diagnosis_keys.extend(
            key for key in ctx.client.data_keys(prefix)
            if to_text(key).endswith(("/Error", "/Status")))
    if diagnosis_keys:
        diagnosis_memory = ctx.client.memory_values(diagnosis_keys)
        missing = [key for key in diagnosis_keys if diagnosis_memory.get(key) is None]
        active = [key for key in diagnosis_keys if active_value(diagnosis_memory.get(key))]
        blocking_missing = [key for key in missing
                            if not _explicit_non_motion_diagnosis(key)]
        blocking_active = [key for key in active
                           if not _explicit_non_motion_diagnosis(key)]
        ignored_memory = [key for key in active
                          if _explicit_non_motion_diagnosis(key)]
        metrics["diagnosis_memory_active"] = active
        metrics["diagnosis_memory_ignored_non_motion"] = ignored_memory
        _append_unique(diagnosis_ignored, ignored_memory)
        if blocking_missing:
            raise SafetyAbort("最新运动相关诊断键有 %d 项无法读取" %
                              len(blocking_missing))
        if blocking_active:
            raise SafetyAbort("最新运动相关诊断键有 %d 项非零：%s" %
                              (len(blocking_active),
                               ", ".join(to_text(key) for key in blocking_active[:4])))
    metrics["diagnosis_ignored_non_motion"] = diagnosis_ignored
    temperatures = temperature_snapshot(ctx.client, names)
    metrics["joint_temperatures"] = temperatures
    warn_at = float(thresholds["joint_temperature_warn_c"])
    for row in temperatures:
        if (row["temperature_c"] is None or row["temperature_status"] is None or
                row["temperature_status"] >= 1 or row["temperature_c"] >= warn_at):
            raise SafetyAbort("最新关节温度/状态不允许运动：%s" % row["joint"])
    previous_fall_baseline = ctx.runtime.get("fall_event_baseline")
    if previous_fall_baseline:
        metrics["fall_events_since_previous_gate"] = _guard_fall_events(
            ctx, "最新安全门控")
        fall_baseline = previous_fall_baseline
    else:
        fall_baseline = _capture_fall_event_baseline(ctx)
        ctx.runtime["fall_event_baseline"] = fall_baseline
    metrics["fall_event_baseline"] = fall_baseline
    stand_state = ctx.client.memory_value("ALMotion/RobotIsStand", None)
    metrics["robot_is_stand"] = stand_state
    if walking and not _stand_supported(stand_state):
        raise SafetyAbort("机器人当前未检测到双脚支撑")
    return metrics

def _pause_autonomous_life(ctx):
    life, error = ctx.client.try_proxy("ALAutonomousLife")
    if life is None:
        raise SafetyAbort("无法访问 ALAutonomousLife：%s" % error)
    try:
        state = to_text(life.getState())
        if state != "disabled":
            life.setState("disabled")
        time.sleep(0.25)
        verified = to_text(life.getState())
        if verified != "disabled":
            raise SafetyAbort("Autonomous Life 未能确认进入 disabled（当前 %s）" % verified)
        return life, state
    except Exception as exc:
        if isinstance(exc, SafetyAbort):
            raise
        raise SafetyAbort("未能暂停 Autonomous Life：%s" % to_text(exc))

def _verify_motion_protections(motion):
    checks = {}
    errors = {}
    calls = [
        ("fall_manager", "getFallManagerEnabled", ()),
        ("self_collision_left_arm", "getCollisionProtectionEnabled", ("LArm",)),
        ("self_collision_right_arm", "getCollisionProtectionEnabled", ("RArm",)),
        ("external_collision_all", "getExternalCollisionProtectionEnabled", ("All",)),
        ("diagnosis_effect", "getDiagnosisEffectEnabled", ()),
    ]
    for label, method, arguments in calls:
        try:
            checks[label] = bool(getattr(motion, method)(*arguments))
        except Exception as exc:
            checks[label] = None
            errors[label] = to_text(exc)
    disabled = [key for key, value in checks.items() if value is not True]
    if disabled:
        raise SafetyAbort("无法确认全部 ALMotion 安全反射已启用：%s；错误=%s" %
                          (", ".join(disabled), to_text(errors)))
    return {"checks": checks, "errors": errors}

def _enable_walk_protections(motion):
    config = [
        ["ENABLE_FOOT_CONTACT_PROTECTION", True],
        ["ENABLE_STIFFNESS_PROTECTION", True],
    ]
    try:
        motion.setMotionConfig(config)
    except Exception as exc:
        raise SafetyAbort("无法启用行走脚接触/腿部刚度保护：%s" % to_text(exc))
    return {"requested": config, "api_call_succeeded": True,
            "note": "NAOqi 未提供对应 getter，已在本次行走前显式设置为 True"}

def _joint_group(name):
    if name.startswith("Head"):
        return "head"
    if name.startswith("LShoulder") or name.startswith("LElbow") or name in ("LWristYaw", "LHand"):
        return "left_arm"
    if name.startswith("RShoulder") or name.startswith("RElbow") or name in ("RWristYaw", "RHand"):
        return "right_arm"
    return "legs"

def _fresh_joint_temperature(ctx, joint):
    return temperature_snapshot(ctx.client, [joint])[0]

def _guard_joint_temperature(ctx, joint):
    row = _fresh_joint_temperature(ctx, joint)
    temperature = row["temperature_c"]
    status = row["temperature_status"]
    if temperature is None or status is None:
        raise SafetyAbort("%s 温度值或温度状态缺失" % joint)
    if status >= 1:
        raise SafetyAbort("%s 温度状态非零（%s）" % (joint, status))
    warn_at = float(ctx.config["thresholds"]["joint_temperature_warn_c"])
    if temperature >= warn_at:
        raise SafetyAbort("%s 温度 %.1f°C 已达到运动预警阈值 %.1f°C" %
                          (joint, temperature, warn_at))
    return row

def _stop_motion_task(motion, task_id):
    errors = []
    if task_id is None:
        return errors
    try:
        if not motion.isRunning(task_id):
            return errors
    except Exception as exc:
        errors.append("isRunning(%s): %s" % (task_id, to_text(exc)))
    for method in ("killTask", "stop"):
        try:
            getattr(motion, method)(task_id)
        except Exception as exc:
            errors.append("%s(%s): %s" % (method, task_id, to_text(exc)))
            continue
        deadline = time.time() + 1.0
        while time.time() < deadline:
            try:
                if not motion.isRunning(task_id):
                    return []
            except Exception as exc:
                errors.append("%s 后无法复核任务：%s" % (method, to_text(exc)))
                break
            time.sleep(0.05)
        errors.append("%s 后任务 %s 仍在运行" % (method, task_id))
    return errors

def _guard_all_temperatures(ctx, joint_names):
    rows = temperature_snapshot(ctx.client, joint_names)
    warn_at = float(ctx.config["thresholds"]["joint_temperature_warn_c"])
    for row in rows:
        if (row["temperature_c"] is None or row["temperature_status"] is None or
                row["temperature_status"] >= 1 or row["temperature_c"] >= warn_at):
            raise SafetyAbort("运动期间温度/状态异常：%s" % row["joint"])
    return rows

def _balance_sample(ctx, fsr_keys):
    angle_x_key = "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value"
    angle_y_key = "Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value"
    stand_key = "ALMotion/RobotIsStand"
    values = ctx.client.memory_values(list(fsr_keys) + [angle_x_key, angle_y_key, stand_key])
    fsr_values = [safe_float(values.get(key), None) for key in fsr_keys]
    left_values = fsr_values[:4]
    right_values = fsr_values[4:]
    return {
        "angle_x": safe_float(values.get(angle_x_key), None),
        "angle_y": safe_float(values.get(angle_y_key), None),
        "robot_is_stand": values.get(stand_key),
        "fsr_values": fsr_values,
        "left_fsr_total": None if any(item is None for item in left_values) else sum(left_values),
        "right_fsr_total": None if any(item is None for item in right_values) else sum(right_values),
    }

def _balance_limits(ctx, motion):
    try:
        body_mass = safe_float(motion.getMass("Body"), None)
    except Exception as exc:
        raise SafetyAbort("无法读取机器人 Body 质量：%s" % to_text(exc))
    if body_mass is None or body_mass < 3.0 or body_mass > 8.0:
        raise SafetyAbort("机器人 Body 质量缺失或不合理：%s kg" % to_text(body_mass))
    thresholds = ctx.config["thresholds"]
    minimum_total = max(
        float(thresholds["fsr_min_standing_weight_kg"]),
        body_mass * float(thresholds["fsr_standing_min_mass_fraction"]),
    )
    maximum_total = body_mass * float(thresholds["fsr_standing_max_mass_fraction"])
    minimum_each_foot = max(
        float(thresholds["fsr_min_each_foot_kg"]),
        body_mass * float(thresholds["fsr_each_foot_min_mass_fraction"]),
    )
    transition_minimum = max(
        float(thresholds["fsr_min_standing_weight_kg"]),
        body_mass * float(thresholds["walk_min_fsr_fraction"]),
    )
    if minimum_total >= maximum_total or minimum_each_foot * 2.0 > maximum_total:
        raise SafetyAbort("由机器人质量计算出的 FSR 安全阈值无效")
    return {
        "body_mass_kg": body_mass,
        "standing_minimum_total_kg": minimum_total,
        "standing_maximum_total_kg": maximum_total,
        "standing_minimum_each_foot_kg": minimum_each_foot,
        "motion_minimum_total_kg": transition_minimum,
    }

def _safe_robot_position(motion):
    try:
        raw = list(motion.getRobotPosition(False))
    except Exception as exc:
        raise SafetyAbort("无法读取行走里程计：%s" % to_text(exc))
    values = [safe_float(item, None) for item in raw]
    if len(values) < 3 or any(item is None for item in values[:3]):
        raise SafetyAbort("行走里程计必须包含三个有限数值")
    return values[:3]

def _validate_balance_sample(ctx, sample, minimum_total, require_both_feet=False,
                             maximum_total=None, minimum_each_foot=None,
                             require_stand=False):
    fsr_values = sample.get("fsr_values", [])
    if (len(fsr_values) != 8 or
            any(safe_float(value, None) is None or float(value) < 0 for value in fsr_values)):
        raise SafetyAbort("行走监控的八路 FSR 数据缺失或为负值")
    angle_x = safe_float(sample.get("angle_x"), None)
    angle_y = safe_float(sample.get("angle_y"), None)
    left_total = safe_float(sample.get("left_fsr_total"), None)
    right_total = safe_float(sample.get("right_fsr_total"), None)
    if angle_x is None or angle_y is None or left_total is None or right_total is None:
        raise SafetyAbort("行走监控的 IMU/FSR 数据缺失")
    stand_state = sample.get("robot_is_stand")
    if require_stand and not _stand_supported(stand_state):
        raise SafetyAbort("机器人未检测到双脚支撑")
    max_tilt = float(ctx.config["thresholds"]["walk_max_tilt_rad"])
    if abs(angle_x) > max_tilt or abs(angle_y) > max_tilt:
        raise SafetyAbort("行走监控倾角超过 %.2f rad" % max_tilt)
    total = left_total + right_total
    if total < float(minimum_total):
        raise SafetyAbort("行走监控 FSR 总承重 %.3f kg 低于 %.3f kg" %
                          (total, minimum_total))
    if maximum_total is not None and total > float(maximum_total):
        raise SafetyAbort("行走监控 FSR 总承重 %.3f kg 高于合理上限 %.3f kg" %
                          (total, maximum_total))
    if require_both_feet:
        each_min = (float(ctx.config["thresholds"]["fsr_min_each_foot_kg"])
                    if minimum_each_foot is None else float(minimum_each_foot))
        if left_total < each_min or right_total < each_min:
            raise SafetyAbort("稳定站立时单脚 FSR 承重低于 %.3f kg" % each_min)
    return total

def _stable_balance_samples(ctx, fsr_keys, balance_limits, phase, count=5,
                            interval=0.05, require_stand=True):
    rows = []
    totals = []
    for index in range(int(count)):
        _guard_fall_events(ctx, phase)
        row = _balance_sample(ctx, fsr_keys)
        total = _validate_balance_sample(
            ctx, row,
            balance_limits["standing_minimum_total_kg"],
            require_both_feet=True,
            maximum_total=balance_limits["standing_maximum_total_kg"],
            minimum_each_foot=balance_limits["standing_minimum_each_foot_kg"],
            require_stand=require_stand)
        row["sample_index"] = index
        rows.append(row)
        totals.append(total)
        if index + 1 < int(count):
            time.sleep(float(interval))
    return {
        "samples": rows,
        "mean_total_kg": sum(totals) / float(len(totals)),
        "minimum_total_kg": min(totals),
        "maximum_total_kg": max(totals),
    }

def _run_posture_task(ctx, posture, motion, posture_name, speed, joint_names,
                      timeout=15.0, fsr_keys=None, balance_limits=None):
    task_id = None
    started = time.time()
    next_temperature = started
    balance_samples = []
    try:
        task_id = posture.post.goToPosture(posture_name, speed)
        while posture.isRunning(task_id):
            _guard_fall_events(ctx, "%s 姿态任务" % posture_name)
            if fsr_keys is not None and balance_limits is not None:
                row = _balance_sample(ctx, fsr_keys)
                _validate_balance_sample(
                    ctx, row, balance_limits["motion_minimum_total_kg"])
                balance_samples.append(row)
            if time.time() >= next_temperature:
                _guard_all_temperatures(ctx, joint_names)
                next_temperature = time.time() + 0.4
            if time.time() - started >= float(timeout):
                raise SafetyAbort("%s 姿态任务超时" % posture_name)
            time.sleep(0.05)
        _guard_fall_events(ctx, "%s 姿态任务结束" % posture_name)
        _guard_all_temperatures(ctx, joint_names)
        if fsr_keys is not None and balance_limits is not None:
            row = _balance_sample(ctx, fsr_keys)
            _validate_balance_sample(
                ctx, row, balance_limits["motion_minimum_total_kg"])
            balance_samples.append(row)
        actual_posture = to_text(posture.getPosture())
        if actual_posture != posture_name:
            raise SafetyAbort("请求 %s 后实际姿态为 %s" % (posture_name, actual_posture or "未知"))
        return {"task_id": task_id, "duration_s": time.time() - started,
                "actual_posture": actual_posture,
                "balance_samples": balance_samples}
    except BaseException as exc:
        errors = _stop_motion_task(posture, task_id)
        try:
            motion.stopMove()
        except Exception as stop_exc:
            errors.append("stopMove: %s" % to_text(stop_exc))
        if errors:
            ctx.logger.error("姿态任务清理失败：%s" % "; ".join(errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且姿态任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(errors)))
        raise

def _run_wakeup_task(ctx, motion, posture, joint_names, fsr_keys, balance_limits,
                     timeout=20.0):
    task_id = None
    started = time.time()
    next_temperature = started
    samples = []
    try:
        task_id = motion.post.wakeUp()
        if task_id is None:
            raise SafetyAbort("wakeUp 未返回可监控的任务编号")
        while True:
            try:
                running = bool(motion.isRunning(task_id))
            except Exception as exc:
                raise SafetyAbort("无法确认 wakeUp 任务状态：%s" % to_text(exc))
            row = _balance_sample(ctx, fsr_keys)
            row.update({"elapsed_s": time.time() - started, "task_running": running})
            samples.append(row)
            _guard_fall_events(ctx, "wakeUp")
            _validate_balance_sample(
                ctx, row, balance_limits["motion_minimum_total_kg"])
            if time.time() >= next_temperature:
                _guard_all_temperatures(ctx, joint_names)
                next_temperature = time.time() + 0.4
            if not running:
                break
            if time.time() - started >= float(timeout):
                raise SafetyAbort("wakeUp 任务超过 %.1f 秒超时" % float(timeout))
            time.sleep(0.05)
        if not bool(motion.robotIsWakeUp()):
            raise SafetyAbort("wakeUp 任务结束后 robotIsWakeUp 仍为 False")
        actual_posture = to_text(posture.getPosture())
        if actual_posture != "StandInit":
            raise SafetyAbort("wakeUp 后实际姿态为 %s，非 StandInit" %
                              (actual_posture or "未知"))
        _guard_fall_events(ctx, "wakeUp 结束")
        final_sample = _balance_sample(ctx, fsr_keys)
        final_total = _validate_balance_sample(
            ctx, final_sample,
            balance_limits["standing_minimum_total_kg"],
            require_both_feet=True,
            maximum_total=balance_limits["standing_maximum_total_kg"],
            minimum_each_foot=balance_limits["standing_minimum_each_foot_kg"],
            require_stand=True)
        return {
            "task_id": task_id,
            "duration_s": time.time() - started,
            "robot_is_wake_up": True,
            "actual_posture": actual_posture,
            "final_fsr_total_kg": final_total,
            "final_balance": final_sample,
            "samples": samples,
        }
    except BaseException as exc:
        errors = _stop_motion_task(motion, task_id)
        try:
            motion.stopMove()
        except Exception as stop_exc:
            errors.append("stopMove: %s" % to_text(stop_exc))
        if errors:
            ctx.logger.error("wakeUp 任务清理失败：%s" % "; ".join(errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且 wakeUp 任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(errors)))
        raise

def _run_rest_task(ctx, motion, joint_names, fsr_keys, balance_limits, timeout=10.0):
    task_id = None
    started = time.time()
    next_temperature = started
    samples = []
    try:
        task_id = motion.post.rest()
        if task_id is None:
            raise SafetyAbort("rest 未返回可监控的任务编号")
        while True:
            try:
                running = bool(motion.isRunning(task_id))
            except Exception as exc:
                raise SafetyAbort("无法确认 rest 任务状态：%s" % to_text(exc))
            row = _balance_sample(ctx, fsr_keys)
            row.update({"elapsed_s": time.time() - started, "task_running": running})
            samples.append(row)
            _guard_fall_events(ctx, "rest")
            _validate_balance_sample(
                ctx, row, balance_limits["motion_minimum_total_kg"])
            if time.time() >= next_temperature:
                _guard_all_temperatures(ctx, joint_names)
                next_temperature = time.time() + 0.4
            if not running:
                break
            if time.time() - started >= float(timeout):
                raise SafetyAbort("rest 任务超过 %.1f 秒超时" % float(timeout))
            time.sleep(0.05)
        if bool(motion.robotIsWakeUp()):
            raise SafetyAbort("rest 任务结束后 robotIsWakeUp 仍为 True")
        final_stiffness = [safe_float(item, None) for item in motion.getStiffnesses("Body")]
        if (len(final_stiffness) != len(joint_names) or
                any(item is None or item > 0.10 for item in final_stiffness)):
            raise SafetyAbort("rest 后无法确认全身刚度已释放")
        return {
            "task_id": task_id,
            "duration_s": time.time() - started,
            "robot_is_wake_up": False,
            "final_body_stiffness": final_stiffness,
            "samples": samples,
        }
    except BaseException as exc:
        errors = _stop_motion_task(motion, task_id)
        try:
            motion.stopMove()
        except Exception as stop_exc:
            errors.append("stopMove: %s" % to_text(stop_exc))
        if errors:
            ctx.logger.error("rest 任务清理失败：%s" % "; ".join(errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且 rest 任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(errors)))
        raise

def _graceful_stop_walk(ctx, motion, task_id, joint_names, fsr_keys,
                        minimum_total=None, timeout=3.0):
    errors = []
    try:
        motion.stopMove()
    except Exception as exc:
        errors.append("stopMove 失败：%s" % to_text(exc))
    if task_id is None:
        return errors
    deadline = time.time() + float(timeout)
    next_temperature = 0.0
    while time.time() < deadline:
        try:
            moving = bool(motion.moveIsActive())
        except Exception as exc:
            errors.append("无法确认 moveIsActive：%s" % to_text(exc))
            moving = True
        try:
            running = bool(motion.isRunning(task_id))
        except Exception as exc:
            errors.append("无法确认行走任务状态：%s" % to_text(exc))
            running = True
        if not moving and not running:
            return errors
        try:
            _guard_fall_events(ctx, "行走减速停止")
            if minimum_total is not None:
                _validate_balance_sample(
                    ctx, _balance_sample(ctx, fsr_keys), minimum_total)
            if time.time() >= next_temperature:
                _guard_all_temperatures(ctx, joint_names)
                next_temperature = time.time() + 0.4
        except Exception as exc:
            errors.append("行走减速停止期间安全监控异常：%s" % to_text(exc))
            break
        time.sleep(0.05)
    try:
        still_moving = bool(motion.moveIsActive())
    except Exception:
        still_moving = True
    try:
        still_running = bool(motion.isRunning(task_id))
    except Exception:
        still_running = True
    if still_moving or still_running:
        errors.append("stopMove 后行走任务未在 %.1f 秒内停止" % float(timeout))
        errors.extend(_stop_motion_task(motion, task_id))
    return errors

def _run_joint_target(ctx, motion, joint, target, duration):
    _guard_joint_temperature(ctx, joint)
    task_id = None
    try:
        task_id = motion.post.angleInterpolation(joint, target, duration, True)
        deadline = time.time() + float(duration) + 3.0
        last_temperature = None
        next_full_temperature = 0.0
        while True:
            last_temperature = _guard_joint_temperature(ctx, joint)
            if time.time() >= next_full_temperature:
                _guard_all_temperatures(
                    ctx, ctx.runtime.get("motion_joint_names", [joint]))
                next_full_temperature = time.time() + 0.25
            _guard_fall_events(ctx, "%s 关节运动" % joint)
            if not motion.isRunning(task_id):
                break
            if time.time() >= deadline:
                raise SafetyAbort("%s 关节插值任务超时" % joint)
            time.sleep(0.05)
        return last_temperature
    except BaseException as exc:
        cleanup_errors = _stop_motion_task(motion, task_id)
        if cleanup_errors:
            ctx.logger.error("关节任务停止失败：%s" % "; ".join(cleanup_errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且异步关节任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(cleanup_errors)))
        raise

def _ramp_joint_stiffness(ctx, motion, joint, stiffness, duration=0.4):
    task_id = None
    try:
        task_id = motion.post.stiffnessInterpolation(joint, stiffness, duration)
        deadline = time.time() + float(duration) + 2.0
        while motion.isRunning(task_id):
            _guard_joint_temperature(ctx, joint)
            _guard_all_temperatures(
                ctx, ctx.runtime.get("motion_joint_names", [joint]))
            _guard_fall_events(ctx, "%s 刚度缓升" % joint)
            if time.time() >= deadline:
                raise SafetyAbort("%s 刚度缓升任务超时" % joint)
            time.sleep(0.05)
        _guard_joint_temperature(ctx, joint)
        _guard_all_temperatures(ctx, ctx.runtime.get("motion_joint_names", [joint]))
        _guard_fall_events(ctx, "%s 刚度缓升结束" % joint)
    except BaseException as exc:
        cleanup_errors = _stop_motion_task(motion, task_id)
        if cleanup_errors:
            ctx.logger.error("刚度任务停止失败：%s" % "; ".join(cleanup_errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且刚度任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(cleanup_errors)))
        raise

def _release_body_stiffness(ctx, motion, joint_names):
    task_id = None
    try:
        task_id = motion.post.stiffnessInterpolation("Body", 0.0, 0.5)
        deadline = time.time() + 2.5
        while motion.isRunning(task_id):
            _guard_all_temperatures(ctx, joint_names)
            _guard_fall_events(ctx, "释放全身刚度")
            if time.time() >= deadline:
                raise SafetyAbort("释放全身刚度任务超时")
            time.sleep(0.05)
        _guard_all_temperatures(ctx, joint_names)
        _guard_fall_events(ctx, "释放全身刚度结束")
        values = [safe_float(item, None) for item in motion.getStiffnesses("Body")]
        if (len(values) != len(joint_names) or
                any(item is None or item > 0.10 for item in values)):
            raise SafetyAbort("无法确认主动关节测试前全身刚度已释放")
        return values
    except BaseException as exc:
        cleanup_errors = _stop_motion_task(motion, task_id)
        if cleanup_errors:
            ctx.logger.error("释放全身刚度任务停止失败：%s" % "; ".join(cleanup_errors))
            if isinstance(exc, Exception):
                raise SafetyAbort("%s；且全身刚度任务未能可靠停止：%s" %
                                  (to_text(exc), "; ".join(cleanup_errors)))
        raise

def _prepare_unstiff_joint(ctx, motion, joint):
    initial_stiffness = safe_float(motion.getStiffnesses(joint)[0], None)
    if initial_stiffness is None:
        raise SafetyAbort("%s 无法读取当前刚度" % joint)
    motion.setStiffnesses(joint, 0.0)
    samples = []
    for _index in range(8):
        value = safe_float(motion.getAngles(joint, True)[0], None)
        if value is None:
            raise SafetyAbort("%s 释放刚度后无法读取当前角度" % joint)
        samples.append(value)
        time.sleep(0.05)
    if max(samples[-4:]) - min(samples[-4:]) > 0.02:
        raise SafetyAbort("%s 释放刚度后仍在移动，未重新上刚度" % joint)
    current = samples[-1]
    motion.setAngles(joint, current, 0.05)
    time.sleep(0.05)
    command = safe_float(motion.getAngles(joint, False)[0], None)
    if command is None or abs(command - current) > 0.03:
        raise SafetyAbort("%s 无法把命令角安全同步到当前传感角" % joint)
    return current, initial_stiffness, samples

def _test_one_joint(ctx, motion, joint, limits, initial_angle, initial_stiffness):
    config = ctx.config["motion"]
    low = safe_float(limits[0], None)
    high = safe_float(limits[1], None)
    initial_angle = safe_float(initial_angle, None)
    if initial_angle is None:
        raise SafetyAbort("%s 初始角不是有限数值" % joint)
    if (low is None or high is None or low >= high or
            initial_angle < low - 0.02 or initial_angle > high + 0.02):
        raise SafetyAbort("%s 初始角 %.4f 超出有效限位 [%.4f, %.4f]" %
                          (joint, initial_angle,
                           low if low is not None else -999.0,
                           high if high is not None else -999.0))
    is_hand = joint.endswith("Hand")
    amplitude = float(config["hand_amplitude"] if is_hand else config["joint_amplitude_rad"])
    margin = 0.05 if is_hand else float(config["limit_margin_rad"])
    duration = float(config["duration_seconds"])
    stiffness = float(config["stiffness"])
    targets = []
    safe_low = low + margin if low + margin <= high - margin else low
    safe_high = high - margin if low + margin <= high - margin else high
    for candidate in (initial_angle + amplitude, initial_angle - amplitude):
        target = max(safe_low, min(safe_high, candidate))
        if safe_float(target, None) is None or abs(target - initial_angle) > amplitude + 1e-6:
            raise SafetyAbort("%s 计算出的目标角无效或超过配置幅度" % joint)
        if abs(target - initial_angle) >= amplitude * 0.35 and all(abs(target - item) > 1e-5 for item in targets):
            targets.append(target)
    row = {
        "joint": joint, "group": _joint_group(joint), "limits": [low, high],
        "initial_angle": initial_angle, "initial_stiffness": initial_stiffness,
        "targets": [], "passed": False,
    }
    if not targets:
        row["error"] = "当前位置太靠近双侧安全边界，无法生成小幅目标"
        return row
    safety_aborted = False
    try:
        row["temperature_before"] = _guard_joint_temperature(ctx, joint)
        _ramp_joint_stiffness(ctx, motion, joint, stiffness)
        applied_stiffness = safe_float(motion.getStiffnesses(joint)[0], None)
        row["applied_stiffness"] = applied_stiffness
        if applied_stiffness is None or abs(applied_stiffness - stiffness) > 0.10:
            raise SafetyAbort("%s 无法确认测试刚度已限制为 %.2f" % (joint, stiffness))
        for target in targets:
            temperature = _run_joint_target(ctx, motion, joint, target, duration)
            measured = safe_float(motion.getAngles(joint, True)[0], None)
            moved = None if measured is None else abs(measured - initial_angle)
            error = None if measured is None else abs(measured - target)
            row["targets"].append({
                "command": target, "measured": measured,
                "moved_from_start": moved, "absolute_error": error,
                "electric_current": safe_float(ctx.client.memory_value(
                    "Device/SubDeviceList/%s/ElectricCurrent/Sensor/Value" % joint, None), None),
            })
            row["temperature_after_target"] = temperature
        _run_joint_target(ctx, motion, joint, initial_angle, duration)
        returned = safe_float(motion.getAngles(joint, True)[0], None)
        row["returned_angle"] = returned
        row["return_error"] = None if returned is None else abs(returned - initial_angle)
        maximum_error = max(item["absolute_error"] for item in row["targets"]
                            if item["absolute_error"] is not None)
        minimum_motion = min(item["moved_from_start"] for item in row["targets"]
                             if item["moved_from_start"] is not None)
        row["max_target_error"] = maximum_error
        row["min_observed_motion"] = minimum_motion
        row["passed"] = (
            maximum_error <= ctx.config["thresholds"]["joint_motion_error_fail_rad"] and
            minimum_motion >= amplitude * ctx.config["thresholds"]["joint_motion_min_fraction"] and
            row["return_error"] is not None and
            row["return_error"] <= ctx.config["thresholds"]["joint_motion_error_fail_rad"]
        )
    except SafetyAbort as exc:
        safety_aborted = True
        row["safety_abort"] = to_text(exc)
        exc.joint_result = row
        raise
    except Exception as exc:
        safety_aborted = True
        row["error"] = to_text(exc)
        abort = SafetyAbort("%s 运动命令/传感读取异常：%s" % (joint, to_text(exc)))
        abort.joint_result = row
        raise abort
    finally:
        cleanup_errors = []
        try:
            motion.setStiffnesses(joint, 0.0)
        except Exception as exc:
            cleanup_errors.append("释放刚度失败：%s" % to_text(exc))
        try:
            actual_stiffness = safe_float(motion.getStiffnesses(joint)[0], None)
            row["stiffness_after_cleanup"] = actual_stiffness
            expected = 0.0
            if actual_stiffness is None or abs(actual_stiffness - expected) > 0.10:
                cleanup_errors.append("清理后刚度 %.3f 与期望 %.3f 不符" %
                                      (actual_stiffness if actual_stiffness is not None else -1.0, expected))
        except Exception as exc:
            cleanup_errors.append("无法复核清理后刚度：%s" % to_text(exc))
        if cleanup_errors:
            row["cleanup_errors"] = cleanup_errors
            row["passed"] = False
            for message in cleanup_errors:
                ctx.logger.error("%s：%s" % (joint, message))
    if cleanup_errors:
        abort = SafetyAbort("%s 清理后无法确认刚度已释放" % joint)
        abort.joint_result = row
        raise abort
    return row

def test_joint_motion(ctx):
    timer = Stopwatch()
    if not getattr(ctx.options, "allow_motion", False):
        return finish(timer, "joints_motion", "关节小幅主动运动", SKIP,
                      "未提供 -AllowMotion；为安全起见没有发送关节运动命令")
    preflight = _motion_preflight(ctx)
    if preflight:
        return finish(timer, "joints_motion", "关节小幅主动运动", SKIP,
                      "安全前置条件不满足：%s" % "；".join(preflight),
                      details=preflight)
    safety_message = (
        "运动测试会逐个驱动头、双臂、双手和双腿关节。必须将 NAO 可靠固定，"
        "四周无人员/线缆/硬物，并全程看护；不要关闭碰撞、跌倒或诊断保护。"
    )
    if not ctx.require_token(safety_message, "MOVE"):
        return finish(timer, "joints_motion", "关节小幅主动运动", SKIP,
                      "操作者未输入 MOVE，运动测试已取消")
    motion = ctx.client.proxy("ALMotion")
    try:
        protections = _verify_motion_protections(motion)
    except SafetyAbort as exc:
        return finish(timer, "joints_motion", "关节小幅主动运动", FAIL,
                      "运动安全反射检查失败：%s" % to_text(exc),
                      details=[to_text(exc)])
    names = [to_text(name) for name in motion.getBodyNames("Body")]
    command_names = [name for name in names if name != "RHipYawPitch" or "LHipYawPitch" not in names]
    rows = []
    aborted = None
    cleanup_errors = []
    completed = False
    fresh_safety_snapshot = None
    protections_after_life_disabled = None
    try:
        life, life_state = _pause_autonomous_life(ctx)
    except SafetyAbort as exc:
        return finish(timer, "joints_motion", "关节小幅主动运动", SKIP,
                      "无法建立安全的自主行为状态：%s" % to_text(exc),
                      metrics={"protections": protections}, details=[to_text(exc)])
    try:
        time.sleep(0.5)
        protections_after_life_disabled = _verify_motion_protections(motion)
        fresh_safety_snapshot = _fresh_motion_gate(ctx, motion, walking=False)
        ctx.runtime["motion_joint_names"] = names
        released_stiffness = _release_body_stiffness(ctx, motion, names)
        for joint in command_names:
            ctx.logger.info("小幅测试关节 %s" % joint)
            try:
                current_angle, current_stiffness, settling_samples = _prepare_unstiff_joint(
                    ctx, motion, joint)
                limits_raw = motion.getLimits(joint)
                limits = limits_raw[0] if limits_raw and isinstance(limits_raw[0], (list, tuple)) else limits_raw
                if not limits or len(limits) < 2:
                    raise SafetyAbort("%s 无法读取有效关节限位" % joint)
                row = _test_one_joint(
                    ctx, motion, joint, limits, current_angle, current_stiffness,
                )
                row["unstiff_settling_samples"] = settling_samples
                rows.append(row)
                if not row.get("passed"):
                    aborted = "%s 未达到跟踪标准；已停止后续关节" % joint
                    ctx.logger.error("运动测试安全中止：%s" % aborted)
                    break
            except SafetyAbort as exc:
                aborted = to_text(exc)
                rows.append(getattr(exc, "joint_result", {
                    "joint": joint, "passed": False, "safety_abort": aborted}))
                ctx.logger.error("运动测试安全中止：%s" % aborted)
                break
        left_hip_ok = any(row.get("joint") == "LHipYawPitch" and row.get("passed") for row in rows)
        if left_hip_ok and "RHipYawPitch" in names:
            rows.append({"joint": "RHipYawPitch", "alias_of": "LHipYawPitch",
                         "passed": True, "note": "同一耦合物理机构，未重复驱动"})
        post_temperatures = temperature_snapshot(ctx.client, names)
        for temperature in post_temperatures:
            if (temperature["temperature_c"] is None or temperature["temperature_status"] is None or
                    temperature["temperature_status"] >= 1 or
                    temperature["temperature_c"] >= ctx.config["thresholds"]["joint_temperature_warn_c"]):
                aborted = aborted or ("运动后温度检查未通过：%s" % temperature["joint"])
                break
        completed = True
    except SafetyAbort as exc:
        aborted = aborted or to_text(exc)
        ctx.logger.error("运动测试安全中止：%s" % aborted)
    except Exception as exc:
        aborted = aborted or ("未预期的运动会话异常：%s" % to_text(exc))
        ctx.logger.error(aborted)
    finally:
        try:
            motion.stopMove()
        except Exception as exc:
            cleanup_errors.append("stopMove 失败：%s" % to_text(exc))
        try:
            motion.setStiffnesses("Body", 0.0)
        except Exception as exc:
            cleanup_errors.append("释放全身刚度失败：%s" % to_text(exc))
        try:
            final_stiffness = [safe_float(item, None) for item in motion.getStiffnesses("Body")]
            if (not final_stiffness or any(item is None or item > 0.10 for item in final_stiffness)):
                cleanup_errors.append("无法确认运动会话后全身刚度已释放")
        except Exception as exc:
            final_stiffness = None
            cleanup_errors.append("无法复核运动会话后全身刚度：%s" % to_text(exc))
        ctx.logger.warning("运动会话结束后 Autonomous Life 保持 disabled，须由操作者在安全区域手动恢复")
    failed = [row for row in rows if not row.get("passed")]
    if cleanup_errors:
        failed.append({"cleanup_errors": cleanup_errors})
    artifact = ctx.write_json_artifact("joint_motion_results.json", rows)
    if aborted:
        status, summary = FAIL, "因安全条件变化而中止：%s" % aborted
    elif failed:
        status, summary = FAIL, "%d/%d 个关节未达到小幅运动跟踪标准" % (len(failed), len(rows))
    else:
        status, summary = PASS, "%d 个 API 关节名称覆盖的物理关节均在安全范围内完成小幅运动并回位" % len(rows)
    if status == FAIL or cleanup_errors:
        ctx.runtime["motion_intervention_required"] = True
        ctx.announcer.say("关节运动测试已经中止，请人工确认机器人安全。",
                          "Joint motion stopped. Confirm the robot is safe.", asynchronous=True)
    return finish(timer, "joints_motion", "关节小幅主动运动", status, summary,
                  {"joints": rows, "safety_abort": aborted,
                   "cleanup_errors": cleanup_errors, "protections": protections,
                   "protections_after_life_disabled": protections_after_life_disabled,
                   "fresh_safety_snapshot": fresh_safety_snapshot,
                   "stiffness_after_initial_release": locals().get("released_stiffness"),
                   "completed": completed,
                   "final_body_stiffness": locals().get("final_stiffness"),
                   "autonomous_life_initial_state": life_state,
                   "autonomous_life_final_state": "disabled",
                   "post_temperatures": locals().get("post_temperatures")},
                  [safety_message,
                   "运动后 Autonomous Life 保持 disabled；请在机器人回到安全区域后人工恢复。"],
                  [artifact])

def test_walk(ctx):
    timer = Stopwatch()
    if not getattr(ctx.options, "allow_walk", False):
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "未提供 -AllowWalk；没有执行站立或行走")
    if not getattr(ctx.options, "allow_motion", False):
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "行走还需要同时提供 -AllowMotion")
    if ctx.assume_yes:
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "行走口令禁止由 -AssumeYes 旁路；必须由现场操作者手动输入")
    preflight = _motion_preflight(ctx, walking=True)
    if preflight:
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "安全前置条件不满足：%s" % "；".join(preflight), details=preflight)
    robot_id = to_text(ctx.robot.get("robot_id", "NAO"))
    token = "WALK-%s" % robot_id
    safety_message = (
        "请将 NAO 移到平整防滑地面，确保前方至少两米、四周至少一米无障碍，电源线已拔除，"
        "并全程监控。不要通过推倒机器人测试保护功能。"
    )
    if not ctx.require_token(safety_message, token):
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "操作者未输入 %s，行走测试已取消" % token)
    motion = ctx.client.proxy("ALMotion")
    posture = ctx.client.proxy("ALRobotPosture")
    try:
        protections = _verify_motion_protections(motion)
    except SafetyAbort as exc:
        return finish(timer, "walk", "站立与短距离行走", FAIL,
                      "运动安全反射检查失败：%s" % to_text(exc), details=[to_text(exc)])
    try:
        life, life_state = _pause_autonomous_life(ctx)
    except SafetyAbort as exc:
        return finish(timer, "walk", "站立与短距离行走", SKIP,
                      "无法建立安全的自主行为状态：%s" % to_text(exc),
                      metrics={"protections": protections}, details=[to_text(exc)])
    samples = []
    metrics = {"requested_distance_m": ctx.config["motion"]["walk_distance_m"],
               "protections": protections,
               "autonomous_life_initial_state": life_state,
               "autonomous_life_final_state": "disabled"}
    error = None
    cleanup_errors = []
    fall_detected = False
    walk_completed = False
    task = None
    joint_names = []
    fsr_keys = [
        "Device/SubDeviceList/%s/FSR/%s/Sensor/Value" % (foot, position)
        for foot in ("LFoot", "RFoot")
        for position in ("FrontLeft", "FrontRight", "RearLeft", "RearRight")
    ]
    try:
        joint_names = [to_text(name) for name in motion.getBodyNames("Body")]
        if not joint_names:
            raise SafetyAbort("无法获取行走监控所需的关节列表")
        metrics["protections_after_life_disabled"] = _verify_motion_protections(motion)
        metrics["balance_limits"] = _balance_limits(ctx, motion)
        metrics["walk_specific_protections"] = _enable_walk_protections(motion)
        metrics["fresh_safety_before_wakeup"] = _fresh_motion_gate(ctx, motion, walking=False)
        metrics["balance_before_wakeup"] = _stable_balance_samples(
            ctx, fsr_keys, metrics["balance_limits"], "wakeUp 前稳定性",
            require_stand=False)
        metrics["wakeup_task"] = _run_wakeup_task(
            ctx, motion, posture, joint_names, fsr_keys, metrics["balance_limits"])
        metrics["fresh_safety_after_wakeup"] = _fresh_motion_gate(ctx, motion, walking=True)
        time.sleep(0.6)
        standing_samples = _stable_balance_samples(
            ctx, fsr_keys, metrics["balance_limits"], "StandInit 稳定性")
        standing = standing_samples["samples"][-1]
        standing_total_min = metrics["balance_limits"]["standing_minimum_total_kg"]
        fsr_total = standing_samples["mean_total_kg"]
        metrics["standing_balance"] = standing_samples
        metrics["standing_fsr_total_kg"] = fsr_total
        if any(abs(row["angle_x"]) > 0.20 or abs(row["angle_y"]) > 0.20
               for row in standing_samples["samples"]):
            raise SafetyAbort("StandInit 后 IMU 倾角缺失或超出 0.20 rad")
        minimum_walk_fsr = max(
            float(ctx.config["thresholds"]["fsr_min_standing_weight_kg"]),
            fsr_total * float(ctx.config["thresholds"]["walk_min_fsr_fraction"]),
        )
        metrics["minimum_fsr_during_walk_kg"] = minimum_walk_fsr
        before = _safe_robot_position(motion)
        metrics["odometry_before"] = before
        distance = float(ctx.config["motion"]["walk_distance_m"])
        speed = float(ctx.config["motion"]["walk_speed_fraction"])
        task = motion.post.moveTo(distance, 0.0, 0.0, [["MaxStepFrequency", speed]])
        started = time.time()
        next_temperature = started
        while time.time() - started < 20.0:
            moving = bool(motion.moveIsActive())
            running = bool(motion.isRunning(task))
            row = _balance_sample(ctx, fsr_keys)
            row.update({"elapsed_s": time.time() - started,
                        "moving": moving, "task_running": running})
            samples.append(row)
            _guard_fall_events(ctx, "短距离行走")
            _validate_balance_sample(
                ctx, row, minimum_walk_fsr, require_stand=True)
            if time.time() >= next_temperature:
                metrics["latest_temperatures_during_walk"] = _guard_all_temperatures(ctx, joint_names)
                next_temperature = time.time() + 0.4
            if not moving and not running:
                break
            time.sleep(0.05)
        if motion.moveIsActive() or motion.isRunning(task):
            raise SafetyAbort("行走超过 20 秒超时")
        if not samples:
            raise SafetyAbort("行走任务未产生监控样本")
        after = _safe_robot_position(motion)
        metrics["odometry_after"] = after
        metrics["odometry_delta"] = [after[index] - before[index] for index in range(min(len(before), len(after)))]
        metrics["max_abs_angle_x"] = max(abs(row["angle_x"]) for row in samples if row["angle_x"] is not None)
        metrics["max_abs_angle_y"] = max(abs(row["angle_y"]) for row in samples if row["angle_y"] is not None)
        time.sleep(0.35)
        final_stability = []
        for _index in range(8):
            _guard_fall_events(ctx, "行走后稳定性")
            final_row = _balance_sample(ctx, fsr_keys)
            _validate_balance_sample(
                ctx, final_row, standing_total_min, require_both_feet=True,
                maximum_total=metrics["balance_limits"]["standing_maximum_total_kg"],
                minimum_each_foot=metrics["balance_limits"]["standing_minimum_each_foot_kg"],
                require_stand=True)
            final_stability.append(final_row)
            time.sleep(0.05)
        metrics["final_stability_samples"] = final_stability
        metrics["temperatures_after_walk"] = _guard_all_temperatures(ctx, joint_names)
        walk_completed = True
    except SafetyAbort as exc:
        error = to_text(exc)
        if "跌倒" in error:
            fall_detected = True
        ctx.logger.error("行走测试安全中止：%s" % error)
    except Exception as exc:
        error = "未预期的行走会话异常：%s" % to_text(exc)
        ctx.logger.error(error)
    finally:
        cleanup_errors.extend(_graceful_stop_walk(
            ctx, motion, task, joint_names, fsr_keys,
            locals().get("minimum_walk_fsr")))
        if walk_completed and not fall_detected and error is None and not cleanup_errors:
            try:
                metrics["crouch_task"] = _run_posture_task(
                    ctx, posture, motion, "Crouch", 0.4, joint_names,
                    fsr_keys=fsr_keys, balance_limits=metrics["balance_limits"])
                metrics["rest_task"] = _run_rest_task(
                    ctx, motion, joint_names, fsr_keys, metrics["balance_limits"])
                metrics["robot_is_wake_up_after_rest"] = False
                metrics["final_body_stiffness"] = metrics["rest_task"]["final_body_stiffness"]
            except Exception as exc:
                cleanup_errors.append("行走后 Crouch/Rest 失败：%s" % to_text(exc))
        elif fall_detected:
            ctx.logger.error("检测到跌倒：未再发送 Crouch/Rest 姿态命令，请扶稳并检查机器人")
        else:
            ctx.logger.warning("行走未完整完成：未再发送新的姿态命令，请安全处置")
        if cleanup_errors:
            suffix = "；".join(cleanup_errors)
            error = (error + "；" + suffix) if error else suffix
        ctx.logger.warning("行走会话结束后 Autonomous Life 保持 disabled，须由操作者在安全区域手动恢复")
    operator_ok = None
    if error is None:
        operator_ok = ctx.ask_yes_no("机器人是否稳定完成短距离前行，且无摔倒、打滑、异常抖动或机械异响？")
    metrics["operator_confirmation"] = operator_ok
    metrics["fall_detected"] = fall_detected
    metrics["cleanup_errors"] = cleanup_errors
    intervention_required = bool(error or operator_ok is False)
    metrics["manual_intervention_required"] = intervention_required
    if intervention_required:
        ctx.runtime["motion_intervention_required"] = True
        if error:
            ctx.announcer.say("行走测试已经中止，请扶稳机器人并人工安全处置",
                              "Walking stopped. Support the robot and intervene safely.", asynchronous=True)
    artifact = ctx.write_json_artifact("walk_samples.json", {"metrics": metrics, "samples": samples, "error": error})
    if error:
        status, summary = FAIL, "行走测试中止/失败：%s" % error
    elif operator_ok is False:
        status, summary = FAIL, "操作者确认行走存在不稳定、打滑、抖动或异响"
    elif not metrics.get("odometry_delta") or metrics["odometry_delta"][0] < 0.03:
        status, summary = WARN, "动作已完成，但里程计前向增量不足 0.03 米"
    else:
        status, summary = PASS, "机器人完成短距离低速前行并安全 Crouch/Rest"
    return finish(timer, "walk", "站立与短距离行走", status, summary,
                  metrics, [safety_message,
                            "行走后 Autonomous Life 保持 disabled；请在安全区域人工恢复"],
                  [artifact])
