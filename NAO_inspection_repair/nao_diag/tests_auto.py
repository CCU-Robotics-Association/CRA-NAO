# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import os
import time
from .client import normalize_battery_percent, pairs_to_dict
from .compat import mean, safe_float, stddev, to_text
from .model import ERROR, FAIL, PASS, SKIP, WARN, Stopwatch
from .tests_common import (active_value, finish, rgb_statistics, sample_memory,
                           statistics, temperature_snapshot, write_rgb_bmp)

def test_connection(ctx):
    timer = Stopwatch()
    metrics = {"ip": ctx.client.ip, "port": ctx.client.port}
    try:
        metrics["tcp_latency_ms"] = ctx.client.tcp_probe(timeout=3.0)
    except Exception as exc:
        return finish(timer, "connection", "网络与 NAOqi 连接", FAIL,
                      "无法连接 NAOqi 端口：%s" % to_text(exc), metrics)
    try:
        system = ctx.client.proxy("ALSystem")
        metrics["naoqi_version"] = to_text(system.systemVersion())
        started = time.time()
        rpc_latencies = []
        for _index in range(5):
            call_start = time.time()
            system.systemVersion()
            rpc_latencies.append((time.time() - call_start) * 1000.0)
        metrics["rpc_latency_ms"] = {
            "count": len(rpc_latencies), "mean": mean(rpc_latencies),
            "max": max(rpc_latencies), "total": (time.time() - started) * 1000.0,
        }
    except Exception as exc:
        return finish(timer, "connection", "网络与 NAOqi 连接", FAIL,
                      "TCP 可达，但 NAOqi RPC 失败：%s" % to_text(exc), metrics)
    status = PASS if metrics["rpc_latency_ms"]["max"] <= 800.0 else WARN
    summary = "NAOqi %s 可连接，RPC 最大延迟 %.1f ms" % (
        metrics["naoqi_version"], metrics["rpc_latency_ms"]["max"])
    return finish(timer, "connection", "网络与 NAOqi 连接", status, summary, metrics)

def test_system(ctx):
    timer = Stopwatch()
    metrics = {}
    details = []
    system = ctx.client.proxy("ALSystem")
    for method, key in (("systemVersion", "naoqi_version"),
                        ("robotName", "robot_name"),
                        ("timezone", "timezone"),
                        ("freeMemory", "free_memory_kb"),
                        ("totalMemory", "total_memory_kb")):
        try:
            metrics[key] = to_text(getattr(system, method)())
        except Exception as exc:
            details.append("ALSystem.%s: %s" % (method, to_text(exc)))
    try:
        metrics["disk_free"] = system.diskFree(False)
    except Exception as exc:
        details.append("ALSystem.diskFree: %s" % to_text(exc))
    try:
        config = ctx.client.proxy("ALMotion").getRobotConfig()
        if isinstance(config, (list, tuple)) and len(config) == 2:
            metrics["robot_config"] = dict(zip([to_text(item) for item in config[0]], config[1]))
        else:
            metrics["robot_config"] = config
    except Exception as exc:
        details.append("ALMotion.getRobotConfig: %s" % to_text(exc))
    model, model_error = ctx.client.try_proxy("ALRobotModel")
    if model is not None:
        for method in ("getRobotType", "getRobotModel"):
            try:
                metrics["robot_type"] = to_text(getattr(model, method)())
                break
            except Exception:
                pass
    elif model_error:
        details.append("ALRobotModel 不可用：%s" % model_error)
    life, _error = ctx.client.try_proxy("ALAutonomousLife")
    if life is not None:
        try:
            metrics["autonomous_life_state"] = to_text(life.getState())
        except Exception:
            pass
    ctx.robot["naoqi_version"] = metrics.get("naoqi_version")
    ctx.robot["robot_name"] = metrics.get("robot_name")
    status = PASS if metrics.get("naoqi_version") else WARN
    return finish(timer, "system", "机器人身份与系统", status,
                  "已读取机器人名称、型号配置和系统版本", metrics, details)

def test_services(ctx):
    timer = Stopwatch()
    services = [
        "ALMemory", "ALSystem", "ALMotion", "ALTextToSpeech", "ALAudioDevice",
        "ALAudioPlayer", "ALVideoDevice", "ALLeds", "ALTouch", "ALSonar",
        "ALBattery", "ALDiagnosis", "ALRobotPosture", "ALBodyTemperature",
        "ALNotificationManager",
    ]
    required = set(["ALMemory", "ALSystem", "ALMotion", "ALTextToSpeech",
                    "ALAudioDevice", "ALVideoDevice", "ALLeds"])
    available = []
    missing = {}
    for service in services:
        _proxy, error = ctx.client.try_proxy(service)
        if error:
            missing[service] = error
        else:
            available.append(service)
    missing_required = sorted(required.intersection(missing))
    if missing_required:
        status = FAIL
        summary = "缺少必需服务：%s" % ", ".join(missing_required)
    elif missing:
        status = WARN
        summary = "核心服务正常；%d 个可选服务不可用" % len(missing)
    else:
        status = PASS
        summary = "已探测的 %d 个 NAOqi 服务均可用" % len(services)
    return finish(timer, "services", "NAOqi 服务完整性", status, summary,
                  {"available": available, "missing": missing})

def _diagnosis_rows(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]

def _diagnosis_key_subject(key):
    parts = [part for part in to_text(key).split("/") if part]
    if len(parts) >= 4 and parts[0] == "Diagnosis":
        return parts[-2]
    return to_text(key)

def _add_unique_text(target, values):
    for value in values:
        value = to_text(value)
        if value and value not in target:
            target.append(value)

def test_diagnosis(ctx, test_id="diagnosis", label="内置诊断与系统通知",
                   artifact_name="diagnosis_snapshot.json"):
    timer = Stopwatch()
    metrics = {"api": {}, "active_error_keys": {}, "temperature_error_keys": {},
               "notifications": []}
    details = []
    severe = []
    fault_subjects = []
    warnings = []
    diagnosis, diagnosis_error = ctx.client.try_proxy("ALDiagnosis")
    if diagnosis is not None:
        for method in ("getDiagnosisStatus", "getPassiveDiagnosis", "getActiveDiagnosis"):
            try:
                value = getattr(diagnosis, method)()
                metrics["api"][method] = value
                if (isinstance(value, (list, tuple)) and len(value) == 2 and
                        safe_float(value[0], None) is not None and isinstance(value[1], (list, tuple))):
                    severity = safe_float(value[0], 0.0)
                    devices = list(value[1])
                    if severity > 0 or devices:
                        severe.append("%s: severity=%s, devices=%s" %
                                      (method, severity, to_text(devices)))
                        if devices:
                            _add_unique_text(fault_subjects, devices)
                        else:
                            _add_unique_text(fault_subjects, [method])
                elif _diagnosis_rows(value):
                    severe.append("%s 返回非空且无法识别的结果" % method)
                    _add_unique_text(fault_subjects, [method])
            except Exception as exc:
                metrics["api"][method + "_error"] = to_text(exc)
    else:
        warnings.append("ALDiagnosis 不可用：%s" % diagnosis_error)
    for prefix, bucket_name in (("Diagnosis/Active", "active_error_keys"),
                                ("Diagnosis/Temperature", "temperature_error_keys")):
        keys = [key for key in ctx.client.data_keys(prefix) if to_text(key).endswith(("/Error", "/Status"))]
        values = ctx.client.memory_values(keys)
        active = dict((to_text(key), value) for key, value in values.items() if active_value(value))
        metrics[bucket_name] = active
        if active:
            severe.append("%s 有 %d 个非零诊断键" % (prefix, len(active)))
            _add_unique_text(
                fault_subjects,
                [_diagnosis_key_subject(key) for key in active.keys()],
            )
    notification_proxy, _error = ctx.client.try_proxy("ALNotificationManager")
    if notification_proxy is not None:
        try:
            raw_notifications = notification_proxy.notifications()
            for raw in raw_notifications or []:
                item = pairs_to_dict(raw)
                metrics["notifications"].append(item)
                severity = to_text(item.get("severity") if isinstance(item, dict) else "").lower()
                message = to_text(item.get("message") if isinstance(item, dict) else item)
                if severity in ("error", "critical", "fatal"):
                    severe.append(message)
                    if isinstance(item, dict):
                        subject = (item.get("device") or item.get("name") or
                                   item.get("id") or message)
                    else:
                        subject = message
                    _add_unique_text(fault_subjects, [subject])
                elif severity in ("warning", "warn"):
                    warnings.append(message)
        except Exception as exc:
            details.append("读取通知失败：%s" % to_text(exc))
    metrics["fault_subjects"] = fault_subjects
    metrics["fault_evidence_count"] = len(severe)
    artifact = ctx.write_json_artifact(artifact_name, metrics)
    if severe:
        status = FAIL
        summary = "发现 %d 个诊断故障对象（%d 条证据）" % (
            len(fault_subjects) or len(severe), len(severe))
    elif warnings:
        status = WARN
        summary = "未发现明确故障，但有 %d 项诊断警告" % len(warnings)
    elif diagnosis is None:
        status = WARN
        summary = "无法使用 ALDiagnosis；已检查可用的 ALMemory 诊断键"
    else:
        status = PASS
        summary = "ALDiagnosis、诊断键和系统通知未发现故障"
    details.extend(severe + warnings)
    return finish(timer, test_id, label, status, summary,
                  metrics, details, [artifact])

def test_diagnosis_after(ctx):
    return test_diagnosis(
        ctx, test_id="diagnosis_after", label="运动后诊断与系统通知",
        artifact_name="diagnosis_after_snapshot.json",
    )

def test_battery(ctx, test_id="battery", label="电池与供电快照"):
    timer = Stopwatch()
    metrics = {}
    details = ["电量快照只能检查当前状态，无法证明电池容量和续航"]
    battery, error = ctx.client.try_proxy("ALBattery")
    if battery is not None:
        for method in ("getBatteryCharge", "getBatteryStatus", "getBatteryCurrent"):
            try:
                metrics[method] = getattr(battery, method)()
            except Exception:
                pass
    elif error:
        details.append("ALBattery 不可用：%s" % error)
    keys = [
        "Device/SubDeviceList/Battery/Charge/Sensor/Value",
        "Device/SubDeviceList/Battery/Current/Sensor/Value",
        "Device/SubDeviceList/Battery/Temperature/Sensor/Value",
        "Device/SubDeviceList/Battery/Temperature/Sensor/Status",
        "Device/SubDeviceList/Battery/Charge/Sensor/Status",
        "Diagnosis/Active/Battery/Error",
        "Diagnosis/Temperature/Battery/Error",
    ]
    metrics["memory"] = ctx.client.memory_values(keys)
    percent = normalize_battery_percent(metrics.get("getBatteryCharge"))
    if percent is None:
        percent = normalize_battery_percent(metrics["memory"].get(keys[0]))
    metrics["charge_percent"] = percent
    if test_id == "battery":
        ctx.runtime["battery_percent_start"] = percent
    else:
        start_percent = ctx.runtime.get("battery_percent_start")
        metrics["start_charge_percent"] = start_percent
        metrics["charge_delta_percent"] = (
            None if start_percent is None or percent is None else percent - start_percent)
    fault_keys = [keys[3], keys[5], keys[6]]
    active_error = any(active_value(metrics["memory"].get(key)) for key in fault_keys)
    if active_error:
        status, summary = FAIL, "电池诊断或温度状态异常"
    elif percent is None:
        status, summary = WARN, "未能读取电池电量"
    elif percent < ctx.config["thresholds"]["battery_warn_below_percent"]:
        status, summary = WARN, "电池可读取，但当前电量仅 %.1f%%；请充电后做运动测试" % percent
    else:
        status, summary = PASS, "电池状态可读取，当前电量 %.1f%%" % percent
    ctx.runtime["battery_percent"] = percent
    return finish(timer, test_id, label, status, summary, metrics, details)

def test_battery_after(ctx):
    return test_battery(ctx, test_id="battery_after", label="测试后电池与供电快照")

def test_board_communication(ctx):
    timer = Stopwatch()
    all_keys = ctx.client.data_keys("Device/DeviceList")
    ack_keys = [key for key in all_keys if to_text(key).endswith("/Ack")]
    nack_keys = [key for key in all_keys if to_text(key).endswith("/Nack")]
    if not ack_keys and not nack_keys:
        return finish(timer, "boards", "板卡通信计数器", SKIP,
                      "当前固件未公开板卡 Ack/Nack 计数器")
    first = ctx.client.memory_values(ack_keys + nack_keys)
    time.sleep(float(ctx.config["thresholds"]["board_observation_seconds"]))
    second = ctx.client.memory_values(ack_keys + nack_keys)
    rows = []
    new_nacks = []
    for key in sorted(set(ack_keys + nack_keys)):
        before = safe_float(first.get(key), None)
        after = safe_float(second.get(key), None)
        delta = None if before is None or after is None else after - before
        row = {"key": to_text(key), "before": before, "after": after, "delta": delta}
        rows.append(row)
        if key in nack_keys and delta is not None and delta > 0:
            new_nacks.append(row)
    ack_progress = [row for row in rows if row["key"] in ack_keys and row["delta"] is not None and row["delta"] > 0]
    if new_nacks:
        status, summary = FAIL, "观察期间有 %d 个板卡 Nack 计数增加" % len(new_nacks)
    elif not ack_progress:
        status, summary = WARN, "未见新增 Nack，但观察窗口内 Ack 计数没有变化"
    else:
        status, summary = PASS, "%d 个板卡通信计数有进展，未见新增 Nack" % len(ack_progress)
    return finish(timer, "boards", "板卡通信计数器", status, summary,
                  {"counters": rows})

def test_temperature(ctx, test_id="temperature", label="关节与机体温度",
                     artifact_name="joint_temperatures.json"):
    timer = Stopwatch()
    motion = ctx.client.proxy("ALMotion")
    joints = [to_text(name) for name in motion.getBodyNames("Body")]
    rows = temperature_snapshot(ctx.client, joints)
    warn_at = float(ctx.config["thresholds"]["joint_temperature_warn_c"])
    fail_at = float(ctx.config["thresholds"]["joint_temperature_fail_c"])
    failures = []
    warnings = []
    missing = []
    for row in rows:
        temperature = row["temperature_c"]
        status_value = row["temperature_status"]
        if temperature is None or status_value is None:
            missing.append(row)
        elif status_value >= 1:
            failures.append(row)
        elif temperature is not None and temperature >= fail_at:
            failures.append(row)
        elif temperature is not None and temperature >= warn_at:
            warnings.append(row)
    body_temperature, _error = ctx.client.try_proxy("ALBodyTemperature")
    body_diagnosis = None
    if body_temperature is not None:
        try:
            body_diagnosis = body_temperature.getTemperatureDiagnosis()
            if isinstance(body_diagnosis, (list, tuple)) and body_diagnosis and active_value(body_diagnosis[0]):
                failures.append({"ALBodyTemperature": body_diagnosis})
        except Exception:
            pass
    ctx.runtime["temperature_rows"] = rows
    artifact = ctx.write_json_artifact(artifact_name, rows)
    if missing:
        status, summary = FAIL, "%d 个关节缺少温度值或温度状态；禁止运动测试" % len(missing)
    elif failures:
        status, summary = FAIL, "发现 %d 项过温/温度诊断异常；禁止运动测试" % len(failures)
    elif warnings:
        status, summary = WARN, "%d 个关节温度达到预警阈值；建议冷却" % len(warnings)
    elif not [row for row in rows if row["temperature_c"] is not None]:
        status, summary = WARN, "无法读取关节温度"
    else:
        status, summary = PASS, "%d 个关节的温度与状态正常" % len(rows)
    return finish(timer, test_id, label, status, summary,
                  {"joints": rows, "body_temperature_diagnosis": body_diagnosis,
                   "warn_threshold_c": warn_at, "fail_threshold_c": fail_at},
                  artifacts=[artifact])

def test_temperature_after(ctx):
    return test_temperature(
        ctx, test_id="temperature_after", label="运动后关节与机体温度",
        artifact_name="joint_temperatures_after.json",
    )

def test_joints_static(ctx):
    timer = Stopwatch()
    motion = ctx.client.proxy("ALMotion")
    names = [to_text(name) for name in motion.getBodyNames("Body")]
    sensor = list(motion.getAngles("Body", True))
    command = list(motion.getAngles("Body", False))
    stiffness = list(motion.getStiffnesses("Body"))
    rows = []
    warn_limit = float(ctx.config["thresholds"]["joint_static_error_warn_rad"])
    fail_limit = float(ctx.config["thresholds"]["joint_static_error_fail_rad"])
    failures, warnings = [], []
    for index, name in enumerate(names):
        measured = safe_float(sensor[index] if index < len(sensor) else None, None)
        requested = safe_float(command[index] if index < len(command) else None, None)
        hard = safe_float(stiffness[index] if index < len(stiffness) else None, None)
        error = None if measured is None or requested is None else abs(measured - requested)
        row = {"joint": name, "sensor": measured, "command": requested,
               "absolute_error": error, "stiffness": hard}
        rows.append(row)
        if measured is None or requested is None:
            failures.append(row)
        elif hard is not None and hard >= 0.2 and error is not None and error > fail_limit:
            failures.append(row)
        elif hard is not None and hard >= 0.2 and error is not None and error > warn_limit:
            warnings.append(row)
    artifacts = [ctx.write_json_artifact("joint_static_snapshot.json", rows)]
    try:
        summary_text = to_text(motion.getSummary())
        artifacts.append(ctx.write_text_artifact("almotion_summary.txt", summary_text))
    except Exception:
        pass
    if failures:
        status, summary = FAIL, "%d 个关节的静态传感/跟踪数据异常" % len(failures)
    elif warnings:
        status, summary = WARN, "%d 个已上刚度关节的命令/实测偏差较大" % len(warnings)
    else:
        status, summary = PASS, "%d 个关节的角度、命令值与刚度数据可读取" % len(rows)
    return finish(timer, "joints_static", "关节静态数据", status, summary,
                  {"joints": rows, "warn_error_rad": warn_limit,
                   "fail_error_rad": fail_limit}, artifacts=artifacts)

def test_imu(ctx):
    timer = Stopwatch()
    prefix = "Device/SubDeviceList/InertialSensor/"
    candidates = {
        "AccX": ["AccelerometerX", "AccX"],
        "AccY": ["AccelerometerY", "AccY"],
        "AccZ": ["AccelerometerZ", "AccZ"],
        "GyrX": ["GyroscopeX", "GyrX"],
        "GyrY": ["GyroscopeY", "GyrY"],
        "GyrZ": ["GyroscopeZ", "GyrZ"],
        "AngleX": ["AngleX"],
        "AngleY": ["AngleY"],
    }
    names = ["AccX", "AccY", "AccZ", "GyrX", "GyrY", "GyrZ", "AngleX", "AngleY"]
    available = set(to_text(item) for item in ctx.client.data_keys("InertialSensor"))
    keys = []
    for name in names:
        possible = [prefix + candidate + "/Sensor/Value" for candidate in candidates[name]]
        selected = next((item for item in possible if item in available), possible[-1])
        keys.append(selected)
    sampling = ctx.config["sampling"]
    samples = sample_memory(ctx.client, keys, sampling["imu_samples"],
                            sampling["imu_interval_seconds"])
    metrics = dict((name, statistics(samples[key])) for name, key in zip(names, keys))
    metrics["resolved_keys"] = dict(zip(names, keys))
    missing = [name for name in names if metrics[name]["count"] == 0]
    version = to_text(ctx.robot.get("naoqi_version", ""))
    gyro_z_required = version.startswith("2.8") or version.startswith("3.")
    optional_missing = [name for name in missing if name == "GyrZ" and not gyro_z_required]
    required_missing = [name for name in missing if name not in optional_missing]
    details = []
    status = PASS
    if required_missing:
        status = FAIL
        summary = "惯导数据缺失：%s" % ", ".join(required_missing)
    else:
        acceleration = [metrics[name]["mean"] for name in ("AccX", "AccY", "AccZ")]
        norm = sum(item * item for item in acceleration) ** 0.5
        gyro = [metrics[name]["mean"] for name in ("GyrX", "GyrY", "GyrZ")
                if metrics[name]["mean"] is not None]
        gyro_norm = sum(item * item for item in gyro) ** 0.5
        metrics["acceleration_norm"] = norm
        metrics["gyro_norm"] = gyro_norm
        if not (4.0 <= norm <= 16.0):
            status = WARN
            details.append("静止加速度模长 %.3f m/s² 偏离重力值，请确认机器人是否静止并校准" % norm)
        if gyro_norm > 0.20:
            status = WARN
            details.append("静止陀螺模长 %.3f rad/s 偏大" % gyro_norm)
        if any(abs(metrics[name]["mean"]) > 3.5 for name in ("AngleX", "AngleY")):
            status = FAIL
            details.append("倾角读数超出合理范围")
        if optional_missing:
            status = WARN
            details.append("此旧版硬件/固件未提供有效 GyrZ，已按可选轴处理")
        summary = "惯导 8 路数据完整；加速度模长 %.3f，陀螺模长 %.3f" % (norm, gyro_norm)
        if optional_missing:
            summary = "惯导必需轴数据完整；旧版可选 GyrZ 不可用"
    artifact = ctx.write_json_artifact("imu_samples.json", {
        "samples": dict((name, samples[key]) for name, key in zip(names, keys)),
        "statistics": metrics,
    })
    return finish(timer, "imu", "惯性测量单元 IMU", status, summary,
                  metrics, details, [artifact])

def test_fsr(ctx):
    timer = Stopwatch()
    locations = ["FrontLeft", "FrontRight", "RearLeft", "RearRight"]
    keys = []
    labels = []
    for foot in ("LFoot", "RFoot"):
        for location in locations:
            keys.append("Device/SubDeviceList/%s/FSR/%s/Sensor/Value" % (foot, location))
            labels.append("%s/%s" % (foot, location))
    extra_keys = []
    for foot in ("LFoot", "RFoot"):
        extra_keys.extend([
            "Device/SubDeviceList/%s/FSR/TotalWeight/Sensor/Value" % foot,
            "Device/SubDeviceList/%s/FSR/CenterOfPressure/X/Sensor/Value" % foot,
            "Device/SubDeviceList/%s/FSR/CenterOfPressure/Y/Sensor/Value" % foot,
        ])
    values = ctx.client.memory_values(keys + extra_keys)
    readings = dict((label, safe_float(values.get(key), None))
                    for label, key in zip(labels, keys))
    valid = [value for value in readings.values() if value is not None and value >= 0]
    left_total = sum(value or 0.0 for label, value in readings.items() if label.startswith("LFoot"))
    right_total = sum(value or 0.0 for label, value in readings.items() if label.startswith("RFoot"))
    metrics = {"readings": readings, "left_total": left_total,
               "right_total": right_total, "total": left_total + right_total}
    metrics["firmware_totals_and_center_of_pressure"] = dict(
        (to_text(key), safe_float(values.get(key), None)) for key in extra_keys)
    details = ["机器人未承重时 FSR 接近零是正常现象；站立承重与重心响应仍需人工/姿态测试"]
    ctx.runtime["fsr_data_valid"] = len(valid) == len(keys)
    ctx.runtime["fsr_metrics"] = metrics
    if len(valid) != len(keys):
        status, summary = FAIL, "FSR 数据不完整：%d/%d 路有效" % (len(valid), len(keys))
    elif left_total + right_total <= 0.02:
        status, summary = WARN, "8 路 FSR 可读取但几乎无负载；未证明承重响应"
    else:
        status, summary = PASS, "8 路足底压力数据完整，总读数 %.3f" % (left_total + right_total)
    return finish(timer, "fsr", "足底压力传感器 FSR", status, summary, metrics, details)

def test_sonar(ctx):
    timer = Stopwatch()
    sonar, error = ctx.client.try_proxy("ALSonar")
    if sonar is None:
        return finish(timer, "sonar", "左右声纳", FAIL, "ALSonar 不可用：%s" % error)
    subscription = "nao_acceptance_sonar_%d" % os.getpid()
    keys = ["Device/SubDeviceList/US/Left/Sensor/Value",
            "Device/SubDeviceList/US/Right/Sensor/Value"]
    samples = None
    try:
        sonar.subscribe(subscription)
        time.sleep(0.35)
        if ctx.interactive:
            ctx.announcer.say("请把平整物体放到机器人胸前约四十厘米处", "Place a flat target about forty centimeters in front of me.")
            ctx.wait_enter("请把宽平面物体或手掌放在两个声纳前约 0.40 米处")
        sampling = ctx.config["sampling"]
        samples = sample_memory(ctx.client, keys, sampling["sonar_samples"],
                                sampling["sonar_interval_seconds"])
    finally:
        try:
            sonar.unsubscribe(subscription)
        except Exception:
            pass
    stats = {"left": statistics(samples[keys[0]]),
             "right": statistics(samples[keys[1]])}
    invalid = [side for side in ("left", "right") if stats[side]["count"] == 0]
    details = []
    if invalid:
        status, summary = FAIL, "声纳数据缺失：%s" % ", ".join(invalid)
    else:
        plausible = []
        for side in ("left", "right"):
            value = stats[side]["mean"]
            plausible.append(0.05 <= value <= 3.5)
        if not all(plausible):
            status, summary = FAIL, "声纳返回值超出合理物理范围"
        elif ctx.interactive:
            target_ok = all(0.20 <= stats[side]["mean"] <= 0.80 for side in ("left", "right"))
            stable = all(stats[side]["stddev"] <= 0.10 for side in ("left", "right"))
            if target_ok and stable:
                status, summary = PASS, "左右声纳对 0.40 米标靶的读数合理且稳定"
            else:
                status, summary = WARN, "声纳有数据，但标靶距离/稳定性未达到建议范围"
        else:
            status, summary = PASS, "左右声纳均返回合理距离数据"
            details.append("快速模式仅证明数据通路；建议用 0.40 米平面物体或手掌复测精度")
    artifact = ctx.write_json_artifact("sonar_samples.json", {
        "left": samples[keys[0]], "right": samples[keys[1]], "statistics": stats,
    })
    return finish(timer, "sonar", "左右声纳", status, summary, stats, details, [artifact])

def _capture_camera(ctx, camera_index, camera_name):
    video = ctx.client.proxy("ALVideoDevice")
    sampling = ctx.config["sampling"]
    client_name = "nao_acceptance_%s_%d" % (camera_name, os.getpid())
    handle = None
    try:
        handle = video.subscribeCamera(
            client_name, int(camera_index), int(sampling["camera_resolution"]),
            int(sampling["camera_color_space"]), int(sampling["camera_fps"]),
        )
        time.sleep(0.25)
        frames = []
        for _index in range(3):
            current = video.getImageRemote(handle)
            if not isinstance(current, (list, tuple)) or len(current) < 7:
                raise RuntimeError("相机返回的数据结构无效")
            frames.append(current)
            time.sleep(0.16)
        frame = frames[-1]
        width, height = int(frame[0]), int(frame[1])
        data = frame[6]
        path = ctx.artifact_path("camera_%s.bmp" % camera_name)
        write_rgb_bmp(path, width, height, data)
        stats = rgb_statistics(data)
        stats.update({
            "camera_index": camera_index,
            "width": width,
            "height": height,
            "layers": frame[2],
            "color_space": frame[3],
            "timestamp_seconds": frame[4],
            "timestamp_microseconds": frame[5],
            "artifact": ctx.relative_path(path),
        })
        timestamps = [(item[4], item[5]) for item in frames]
        first_raw = bytearray(frames[0][6])
        last_raw = bytearray(frames[-1][6])
        sampled_difference = []
        for offset in range(0, min(len(first_raw), len(last_raw)), 503):
            sampled_difference.append(abs(first_raw[offset] - last_raw[offset]))
        stats["frame_count"] = len(frames)
        stats["timestamps"] = timestamps
        stats["timestamps_changed"] = len(set(timestamps)) == len(timestamps)
        stats["mean_sampled_frame_difference"] = mean(sampled_difference) if sampled_difference else 0.0
        return stats, None
    except Exception as exc:
        return None, to_text(exc)
    finally:
        if handle:
            try:
                video.unsubscribe(handle)
            except Exception:
                pass

def test_cameras(ctx):
    timer = Stopwatch()
    metrics = {}
    errors = {}
    artifacts = []
    for index, name in ((0, "top"), (1, "bottom")):
        stats, error = _capture_camera(ctx, index, name)
        if error:
            errors[name] = error
        else:
            metrics[name] = stats
            artifacts.append(stats["artifact"])
    if errors:
        status, summary = FAIL, "相机采集失败：%s" % ", ".join(sorted(errors))
    else:
        threshold = ctx.config["thresholds"]
        bad = []
        for name, stats in metrics.items():
            if not (threshold["camera_mean_min"] <= stats["mean"] <= threshold["camera_mean_max"]):
                bad.append("%s 亮度" % name)
            if stats["stddev"] < threshold["camera_stddev_min"]:
                bad.append("%s 对比度" % name)
            if not stats.get("timestamps_changed"):
                bad.append("%s 帧时间戳" % name)
        if bad:
            status, summary = FAIL, "相机帧疑似全黑、全白或无有效画面：%s" % ", ".join(bad)
        else:
            if ctx.interactive:
                ctx.logger.info("相机预览图：%s" % ", ".join(artifacts))
                ctx.announcer.say(
                    "上下摄像头数据已经保存，请在电脑上确认画面清晰",
                    "Camera images were saved. Please confirm that both images are clear.",
                )
                visual_ok = ctx.ask_yes_no(
                    "请打开本次报告 artifacts 目录内的 camera_top.bmp 和 camera_bottom.bmp；"
                    "两张画面是否清晰、无明显坏点且镜头无遮挡"
                )
                metrics["operator_visual_confirmation"] = visual_ok
                if visual_ok:
                    status, summary = PASS, "上下相机数据有效，操作者确认画面清晰"
                else:
                    status, summary = FAIL, "相机数据可采集，但操作者确认画质/镜头异常"
            else:
                status, summary = WARN, "上下相机返回有效 RGB 帧；尚未人工确认清晰度、坏点和污渍"
    details = []
    if errors:
        details.extend("%s: %s" % (key, value) for key, value in errors.items())
    details.append("自动指标不能判断虚焦、污渍和坏点，请在 HTML 报告中打开两张 BMP 人工确认")
    metrics["errors"] = errors
    return finish(timer, "cameras", "上下摄像头", status, summary,
                  metrics, details, artifacts)

def _audio_energy(audio_device):
    methods = ["getFrontMicEnergy", "getRearMicEnergy", "getLeftMicEnergy", "getRightMicEnergy"]
    result = {}
    for method in methods:
        result[method.replace("get", "").replace("MicEnergy", "").lower()] = safe_float(
            getattr(audio_device, method)(), None)
    return result

def test_audio(ctx):
    timer = Stopwatch()
    audio, audio_error = ctx.client.try_proxy("ALAudioDevice")
    player, player_error = ctx.client.try_proxy("ALAudioPlayer")
    if audio is None:
        return finish(timer, "audio", "麦克风与扬声器", FAIL,
                      "ALAudioDevice 不可用：%s" % audio_error)
    try:
        audio.enableEnergyComputation()
    except Exception as exc:
        return finish(timer, "audio", "麦克风与扬声器", FAIL,
                      "无法启用麦克风能量计算：%s" % to_text(exc))
    sample_count = int(ctx.config["sampling"]["audio_samples"])
    interval = float(ctx.config["sampling"]["audio_interval_seconds"])
    baseline = dict((side, []) for side in ("front", "rear", "left", "right"))
    tone = dict((side, []) for side in baseline)
    tone_error = None
    tone_source = None
    try:
        time.sleep(0.4)
        for _index in range(max(4, sample_count // 2)):
            values = _audio_energy(audio)
            for side in baseline:
                if values.get(side) is not None:
                    baseline[side].append(values[side])
            time.sleep(interval)
        playback_errors = []
        for source_name, source in (("ALAudioDevice", audio), ("ALAudioPlayer", player)):
            if source is None:
                continue
            try:
                source.post.playSine(1000, 45, 0, 1.4)
                tone_source = source_name
                break
            except Exception as exc:
                playback_errors.append("%s: %s" % (source_name, to_text(exc)))
        if tone_source is None:
            tone_error = "; ".join(playback_errors) or player_error or "playSine unavailable"
        else:
            for _index in range(sample_count):
                values = _audio_energy(audio)
                for side in tone:
                    if values.get(side) is not None:
                        tone[side].append(values[side])
                time.sleep(interval)
    finally:
        try:
            audio.disableEnergyComputation()
        except Exception:
            pass
    metrics = {"baseline": {}, "during_1khz_tone": {}, "channels": {},
               "tone_source": tone_source}
    responsive = []
    missing = []
    threshold = ctx.config["thresholds"]
    for side in baseline:
        base_stats = statistics(baseline[side])
        tone_stats = statistics(tone[side])
        metrics["baseline"][side] = base_stats
        metrics["during_1khz_tone"][side] = tone_stats
        if base_stats["count"] == 0:
            missing.append(side)
            continue
        base_peak = base_stats["max"] or 0.0
        tone_peak = tone_stats["max"] if tone_stats["count"] else None
        rise = None if tone_peak is None else tone_peak - base_peak
        ratio = None if tone_peak is None else tone_peak / max(base_peak, 1.0)
        metrics["channels"][side] = {"rise": rise, "ratio": ratio}
        if rise is not None and (rise >= threshold["audio_min_energy_rise"] or
                                 ratio >= threshold["audio_min_ratio"]):
            responsive.append(side)
    heard = None
    if ctx.interactive:
        heard = ctx.ask_yes_no("刚才是否清楚、无明显破音地听到 1 kHz 测试音？")
        metrics["operator_heard_clean_tone"] = heard
    if missing:
        status, summary = FAIL, "麦克风能量数据缺失：%s" % ", ".join(missing)
    elif heard is False:
        status, summary = FAIL, "操作者确认扬声器测试音异常"
    elif tone_error:
        status, summary = WARN, "四路麦克风可读取，但自动播放测试音失败"
    elif len(responsive) < 2:
        status, summary = WARN, "四路麦克风可读取，但回录测试音的能量提升不足"
    elif ctx.interactive and heard is True:
        status, summary = PASS, "四路麦克风有数据，至少两路响应测试音，操作者确认扬声器正常"
    else:
        status, summary = WARN, "音频通路有响应；快速模式未人工确认扬声器清晰度"
    details = []
    if tone_error:
        details.append("playSine: %s" % tone_error)
    details.append("机器人自身回录只能作通路筛查；严格验收需外部标准声源和录音分析")
    artifact = ctx.write_json_artifact("audio_energy.json", metrics)
    return finish(timer, "audio", "麦克风与扬声器", status, summary,
                  metrics, details, [artifact])
