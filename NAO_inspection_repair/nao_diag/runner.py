# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import os
import traceback
from .client import NaoClient
from .compat import ensure_dir, now_iso, slugify, timestamp_slug, to_text
from .context import DiagnosticContext
from .log_analysis import analyze_paths, discover_log_files
from .model import ERROR, FAIL, PASS, SKIP, WARN, Stopwatch, make_result, overall_status
from .remote_logs import collect_remote_logs
from .report import build_report_payload, write_reports
from .tests_auto import (test_audio, test_battery, test_battery_after,
                         test_board_communication,
                         test_cameras, test_connection, test_diagnosis,
                         test_diagnosis_after, test_fsr,
                         test_imu, test_joints_static, test_services, test_sonar,
                         test_system, test_temperature, test_temperature_after)
from .tests_common import finish
from .tests_guided import test_bumpers, test_leds, test_touch
from .tests_motion import test_joint_motion, test_walk

def test_remote_logs(ctx):
    timer = Stopwatch()
    paths = []
    collection = None
    details = []
    if getattr(ctx.options, "collect_logs", False):
        collection = collect_remote_logs(
            ctx.client.ip,
            ctx.log_dir,
            user=getattr(ctx.options, "ssh_user", "nao"),
            ssh_port=getattr(ctx.options, "ssh_port", 22),
            key_path=getattr(ctx.options, "ssh_key", None),
            line_count=ctx.config["logging"]["remote_tail_lines"],
            non_interactive=not ctx.interactive,
            logger=ctx.logger,
        )
        paths.extend(collection["collected"])
        for error in collection["errors"]:
            details.append("%s: %s" % (error.get("name"), error.get("error", error.get("return_code"))))
    for root in getattr(ctx.options, "log_dir", []) or []:
        paths.extend(discover_log_files(root))
    paths = sorted(set(os.path.abspath(path) for path in paths if os.path.isfile(path)))
    if not paths:
        if getattr(ctx.options, "collect_logs", False):
            return finish(timer, "logs", "机器人系统日志", WARN,
                          "未能通过 SSH 收集日志；ALDiagnosis 快照仍已保存",
                          {"collection": collection}, details)
        return finish(timer, "logs", "机器人系统日志", SKIP,
                      "未要求 SSH 日志采集；已通过 ALDiagnosis/通知完成稳定 API 检查",
                      details=["需要原生日志时加 -CollectLogs，并推荐配置 -SshKey。"])
    analysis = analyze_paths(
        paths, max_samples=ctx.config["logging"]["max_samples_per_severity"])
    artifact = ctx.write_json_artifact("log_analysis.json", analysis)
    counts = analysis["counts"]
    if counts["critical"]:
        status = FAIL
        summary = "日志发现 %d 条关键级故障线索" % counts["critical"]
    elif counts["error"]:
        status = WARN
        summary = "日志发现 %d 条错误关键词，需结合上下文复核" % counts["error"]
    elif counts["warning"]:
        status = WARN
        summary = "日志发现 %d 条警告关键词，未见关键故障关键词" % counts["warning"]
    else:
        status = PASS
        summary = "扫描 %d 个日志文件、%d 行，未命中故障关键词" % (
            analysis["files_scanned"], analysis["lines_scanned"])
    if collection and collection["errors"]:
        status = WARN if status == PASS else status
        details.append("部分远程日志路径在此固件上不存在或无权读取")
    details.append("NAOqi 文本日志格式非稳定 API；关键词结果仅作为辅助证据")
    metrics = {"analysis": analysis, "source_files": paths, "collection": collection}
    return finish(timer, "logs", "机器人系统日志", status, summary,
                  metrics, details, [artifact])

TEST_SPECS = [
    ("connection", "网络与 NAOqi 连接", test_connection, ("quick", "guided", "full")),
    ("system", "机器人身份与系统", test_system, ("quick", "guided", "full")),
    ("services", "NAOqi 服务完整性", test_services, ("quick", "guided", "full")),
    ("diagnosis", "内置诊断与系统通知", test_diagnosis, ("quick", "guided", "full")),
    ("battery", "电池与供电快照", test_battery, ("quick", "guided", "full")),
    ("boards", "板卡通信计数器", test_board_communication, ("quick", "guided", "full")),
    ("temperature", "关节与机体温度", test_temperature, ("quick", "guided", "full")),
    ("joints_static", "关节静态数据", test_joints_static, ("quick", "guided", "full")),
    ("imu", "惯性测量单元 IMU", test_imu, ("quick", "guided", "full")),
    ("fsr", "足底压力传感器 FSR", test_fsr, ("quick", "guided", "full")),
    ("sonar", "左右声纳", test_sonar, ("quick", "guided", "full")),
    ("cameras", "上下摄像头", test_cameras, ("quick", "guided", "full")),
    ("audio", "麦克风与扬声器", test_audio, ("quick", "guided", "full")),
    ("touch", "头部、左右手整体触摸与胸键", test_touch, ("guided", "full")),
    ("bumpers", "四个脚部碰撞开关", test_bumpers, ("guided", "full")),
    ("leds", "LED 灯组", test_leds, ("guided", "full")),
    ("joints_motion", "关节小幅主动运动", test_joint_motion, ("full",)),
    ("walk", "站立与短距离行走", test_walk, ("full",)),
    ("temperature_after", "运动后关节与机体温度", test_temperature_after, ("full",)),
    ("battery_after", "测试后电池与供电快照", test_battery_after, ("full",)),
    ("diagnosis_after", "运动后诊断与系统通知", test_diagnosis_after, ("full",)),
    ("logs", "机器人系统日志", test_remote_logs, ("quick", "guided", "full")),
]

def list_tests(profile=None):
    return [item for item in TEST_SPECS if profile is None or profile in item[3]]

def _selected_specs(options):
    only = set(item.strip() for item in (getattr(options, "only", "") or "").split(",") if item.strip())
    skip = set(item.strip() for item in (getattr(options, "skip", "") or "").split(",") if item.strip())
    specs = list_tests(options.profile)
    if not getattr(options, "collect_logs", False) and not (getattr(options, "log_dir", []) or []):
        specs = [item for item in specs if item[0] != "logs"]
    if only:
        specs = [item for item in specs if item[0] in only]
    return [item for item in specs if item[0] not in skip]

def _test_error(ctx, test_id, label, timer, exc):
    trace = traceback.format_exc()
    ctx.logger.error("%s 发生未处理异常：%s" % (test_id, to_text(exc)))
    artifact = ctx.write_text_artifact("error_%s.txt" % slugify(test_id), trace)
    return make_result(
        test_id, label, ERROR, "测试程序异常：%s" % to_text(exc),
        details=[trace], artifacts=[artifact], started_at=timer.started_at,
        duration_ms=timer.elapsed_ms(),
    )

def run_robot(robot, config, options):
    robot_id = to_text(robot.get("robot_id") or robot.get("id") or "NAO")
    ip = to_text(robot["ip"])
    port = int(robot.get("port") or getattr(options, "port", 9559))
    robot = dict(robot)
    robot.update({"robot_id": robot_id, "ip": ip, "port": port})
    run_name = "%s_%s" % (timestamp_slug(), slugify(ip))
    output_dir = os.path.abspath(os.path.join(
        getattr(options, "output", "reports"), slugify(robot_id), run_name,
    ))
    ensure_dir(output_dir)
    client = NaoClient(ip, port)
    context = DiagnosticContext(client, robot, config, output_dir, options)
    started_at = now_iso()
    context.logger.info("开始检查 %s (%s:%d)，配置 %s" % (robot_id, ip, port, options.profile))
    for test_id, label, function, _profiles in _selected_specs(options):
        timer = Stopwatch()
        context.logger.info("开始项目 %s - %s" % (test_id, label))
        try:
            result = function(context)
        except KeyboardInterrupt:
            context.logger.warning("用户中断测试")
            raise
        except Exception as exc:
            result = _test_error(context, test_id, label, timer, exc)
        context.results.append(result)
        if test_id in ("joints_motion", "walk") and result["status"] in (FAIL, ERROR):
            context.runtime["motion_intervention_required"] = True
        context.logger.info("完成项目 %s：%s - %s" % (
            test_id, result["status"], result["summary"]))
        if result["status"] == PASS:
            context.announcer.test_passed(label)
        if test_id == "connection" and result["status"] in (FAIL, ERROR):
            context.logger.error("连接失败，后续硬件项目无法执行；提前结束本机检查")
            break
    status = overall_status(context.results)
    context.announcer.final(status, robot_id)
    context.announcer.restore()
    finished_at = now_iso()
    payload = build_report_payload(context, started_at, finished_at)
    paths = write_reports(context, payload)
    context.logger.info("检查完成：%s / %s；HTML 报告：%s" % (
        payload["overall_status"], payload["verdict"], paths["html"]))
    return payload, paths
