# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import time
from .compat import safe_float, to_text
from .model import FAIL, PASS, SKIP, WARN, Stopwatch
from .tests_common import finish

TOUCH_LABELS = {
    "Head/Touch": "头部触摸区域（任意位置）",
    "LHand/Touch": "左手触摸区域（任意位置）",
    "RHand/Touch": "右手触摸区域（任意位置）",
    "ChestBoard/Button": "胸口按钮（短按后立即松开）",
    "LFoot/Bumper/Left": "左脚左侧碰撞开关",
    "LFoot/Bumper/Right": "左脚右侧碰撞开关",
    "RFoot/Bumper/Left": "右脚左侧碰撞开关",
    "RFoot/Bumper/Right": "右脚右侧碰撞开关",
}

TOUCH_GROUPS = {
    "Head/Touch": (
        "Head/Touch/Front", "Head/Touch/Middle", "Head/Touch/Rear",
    ),
    "LHand/Touch": (
        "LHand/Touch/Back", "LHand/Touch/Left", "LHand/Touch/Right",
    ),
    "RHand/Touch": (
        "RHand/Touch/Back", "RHand/Touch/Left", "RHand/Touch/Right",
    ),
}

TOUCH_TEST_SENSORS = (
    "Head/Touch", "LHand/Touch", "RHand/Touch", "ChestBoard/Button",
)


def _sensor_key(sensor):
    return "Device/SubDeviceList/%s/Sensor/Value" % sensor


def _read(ctx, key):
    return safe_float(ctx.client.memory_value(key, None), None)


def _read_members(ctx, members):
    return dict((member, _read(ctx, _sensor_key(member))) for member in members)


def _high_members(values, members):
    return [member for member in members
            if values.get(member) is not None and values[member] >= 0.5]


def _all_members_low(values, members):
    return all(values.get(member) is not None and values[member] < 0.5
               for member in members)

def _wait_sensor_cycle(ctx, sensor, timeout):
    members = TOUCH_GROUPS.get(sensor, (sensor,))
    keys = [_sensor_key(member) for member in members]
    started = time.time()
    initial = _read_members(ctx, members)
    available = [member for member in members if initial.get(member) is not None]
    missing_members = [member for member in members if member not in available]
    peak = dict(initial)
    base = {
        "sensor": sensor,
        "members": list(members),
        "keys": keys,
        "key": " | ".join(keys),
        "initial": initial,
        "missing_members": missing_members,
    }
    if not available:
        base.update({"status": "missing", "peak": peak})
        return base
    is_chest_button = sensor == "ChestBoard/Button"
    if is_chest_button and _high_members(initial, available):
        base.update({"status": "stuck_high", "peak": peak})
        return base
    current = initial
    while (_high_members(current, available) and
           time.time() - started < min(3.0, timeout)):
        time.sleep(0.05)
        current = _read_members(ctx, available)
    if not _all_members_low(current, available):
        base.update({"status": "stuck_high", "peak": peak, "final": current})
        return base
    activated_at = None
    activated_members = []
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        current = _read_members(ctx, available)
        for member in available:
            value = current.get(member)
            if value is not None:
                previous = peak.get(member)
                peak[member] = value if previous is None else max(previous, value)
        high = _high_members(current, available)
        if high:
            activated_members = list(high)
            activated_at = time.time()
            break
        time.sleep(0.04)
    if activated_at is None:
        base.update({"status": "timeout", "peak": peak, "final": current})
        return base

    released = False
    release_deadline = time.time() + (0.8 if is_chest_button else 3.0)
    final_value = current
    while time.time() < release_deadline:
        final_value = _read_members(ctx, available)
        for member in _high_members(final_value, available):
            if member not in activated_members:
                activated_members.append(member)
        if _all_members_low(final_value, available):
            released = True
            break
        time.sleep(0.04)
    base.update({
        "status": "passed" if released else "no_release",
        "peak": peak,
        "final": final_value,
        "activated_members": activated_members,
        "activation_seconds": activated_at - started,
    })
    return base


def _run_sensor_group(ctx, test_id, test_label, sensors):
    timer = Stopwatch()
    if not ctx.interactive:
        return finish(timer, test_id, test_label, SKIP,
                      "该项目需要操作者逐个按压，非交互模式未执行")
    timeout = float(ctx.config["sampling"]["touch_timeout_seconds"])
    rows = []
    ctx.logger.info("%s：每个区域或按键有 %.1f 秒操作时间" % (test_label, timeout))
    for sensor in sensors:
        label = TOUCH_LABELS.get(sensor, sensor)
        instruction = "请操作%s，然后松开" % label
        ctx.logger.info(instruction)
        ctx.announcer.say(instruction, "Activate %s, then release it." % sensor)
        time.sleep(0.35)
        row = _wait_sensor_cycle(ctx, sensor, timeout)
        row["label"] = label
        rows.append(row)
        if row["status"] == "passed":
            ctx.announcer.say("%s通过" % label, "%s passed." % sensor)
        else:
            ctx.logger.warning("%s 未通过：%s" % (label, row["status"]))
            if sensor == "ChestBoard/Button" and row["status"] in ("stuck_high", "no_release"):
                ctx.announcer.say("请立即松开胸口按钮", "Release the chest button immediately.")
    failed = [row for row in rows if row["status"] != "passed"]
    missing = [row for row in rows if row["status"] == "missing"]
    if failed:
        status, summary = FAIL, "%d/%d 个传感位置未完成按下并释放响应" % (len(failed), len(rows))
    elif not rows:
        status, summary = WARN, "没有发现可测试的传感位置"
    else:
        status, summary = PASS, "%d 个传感位置均检测到 0→1→0 响应" % len(rows)
    artifact = ctx.write_json_artifact("%s_cycles.json" % test_id, rows)
    details = []
    if missing:
        details.append("缺失键：%s" % ", ".join(row["key"] for row in missing))
    return finish(timer, test_id, test_label, status, summary,
                  {"sensors": rows, "timeout_seconds": timeout}, details, [artifact])

def test_touch(ctx):
    return _run_sensor_group(
        ctx, "touch", "头部、左右手整体触摸与胸键", TOUCH_TEST_SENSORS)

def test_bumpers(ctx):
    return _run_sensor_group(ctx, "bumpers", "四个脚部碰撞开关", [
        "LFoot/Bumper/Left", "LFoot/Bumper/Right",
        "RFoot/Bumper/Left", "RFoot/Bumper/Right",
    ])

def test_leds(ctx):
    timer = Stopwatch()
    if not ctx.interactive:
        return finish(timer, "leds", "LED 灯组", SKIP,
                      "LED 需要操作者观察颜色、亮度和坏点，非交互模式未执行")
    leds, error = ctx.client.try_proxy("ALLeds")
    if leds is None:
        return finish(timer, "leds", "LED 灯组", FAIL, "ALLeds 不可用：%s" % error)
    errors = []
    available_groups = []
    try:
        available_groups = [to_text(item) for item in leds.listGroups()]
    except Exception:
        pass
    ctx.announcer.say(
        "现在测试眼睛、胸口、脚部和耳部灯光，请观察颜色和坏点",
        "Testing eye, chest, foot, and ear LEDs. Watch the colors and look for dead LEDs.",
    )
    try:
        for color in (0x00FF0000, 0x0000FF00, 0x000000FF, 0x00FFFFFF):
            for group in ("FaceLeds", "ChestLeds", "FeetLeds"):
                try:
                    leds.fadeRGB(group, color, 0.25)
                except Exception as exc:
                    errors.append("%s: %s" % (group, to_text(exc)))
            time.sleep(0.35)
        try:
            leds.fade("EarLeds", 1.0, 0.25)
            time.sleep(0.5)
            leds.fade("EarLeds", 0.0, 0.25)
        except Exception as exc:
            errors.append("EarLeds: %s" % to_text(exc))
    finally:
        for group in ("FaceLeds", "ChestLeds", "FeetLeds", "EarLeds"):
            try:
                leds.reset(group)
            except Exception:
                if group == "FaceLeds":
                    try:
                        leds.fadeRGB(group, 0x00FFFFFF, 0.2)
                    except Exception:
                        pass
    visual_ok = ctx.ask_yes_no("眼睛 RGB、胸灯、双脚灯和双耳蓝灯是否都正常，无坏点/异常暗点？")
    metrics = {"available_groups": available_groups, "api_errors": errors,
               "operator_visual_confirmation": visual_ok}
    if errors:
        status, summary = FAIL, "LED 命令出现 %d 项错误" % len(errors)
    elif not visual_ok:
        status, summary = FAIL, "操作者确认 LED 颜色、亮度或灯点异常"
    else:
        status, summary = PASS, "LED 指令正常，操作者确认全部灯组显示正常"
    return finish(timer, "leds", "LED 灯组", status, summary, metrics, errors)
