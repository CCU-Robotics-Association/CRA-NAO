# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : 命令行参数解析与批量验收
@ Author             : XCrane
"""
from __future__ import print_function, unicode_literals
import argparse
import csv
import io
import sys
from .client import NaoqiUnavailable
from .compat import PY2, console_write, decode_argv, stream_write, to_text
from .config import load_config
from .runner import list_tests, run_robot

class UnicodeArgumentParser(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            stream_write(file or sys.stderr, message)

def build_parser():
    parser = UnicodeArgumentParser(description="NAO 机器人验修工具箱")
    parser.add_argument("--ip", action="append", help="IP 地址")
    parser.add_argument("--port", type=int, default=9559, help="NAOqi 端口，默认 9559")
    parser.add_argument("--robot-id", help="NAO 编号")
    parser.add_argument("--inventory", help="批量机器人 CSV(robot_id,ip,port,notes)")
    parser.add_argument("--profile", choices=("quick", "guided", "full"), default="quick", help="验修模式：quick/guided/full")
    parser.add_argument("--output", default="reports", help="报告根目录")
    parser.add_argument("--config", help="覆盖默认阈值的 JSON")
    parser.add_argument("--interactive", dest="interactive", action="store_true", default=None, help="交互式模式")
    parser.add_argument("--non-interactive", dest="interactive", action="store_false", help="非交互式模式")
    parser.add_argument("--voice", dest="voice", action="store_true", default=True, help="启用 TTS")
    parser.add_argument("--no-voice", dest="voice", action="store_false", help="禁用 TTS")
    parser.add_argument("--language", default="auto", help="TTS 语言：auto/Chinese/English")
    parser.add_argument("--allow-motion", action="store_true", help="允许关节小幅运动")
    parser.add_argument("--allow-walk", action="store_true", help="允许地面短距离行走")
    parser.add_argument("--assume-yes", action="store_true",
                        help="仅旁路 MOVE 口令和等待；禁止行走且不代替人工确认")
    parser.add_argument("--only", help="仅运行逗号分隔的测试 ID")
    parser.add_argument("--skip", help="跳过逗号分隔的测试 ID")
    parser.add_argument("--collect-logs", action="store_true", help="通过 SSH 只读采集系统日志")
    parser.add_argument("--ssh-user", default="nao", help="SSH 用户名")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口，默认 22")
    parser.add_argument("--ssh-key", help="SSH 私钥路径；不支持命令行传输密码")
    parser.add_argument("--log-dir", action="append", default=[], help="额外分析已有日志目录；可重复")
    parser.add_argument("--list-tests", action="store_true", help="列出所有测试 ID")
    parser.add_argument("--verbose", action="store_true", help="启用详细输出")
    return parser

def _read_inventory(path):
    robots = []
    if PY2:
        handle = open(path, "rb")
        marker = handle.read(3)
        if marker != b"\xef\xbb\xbf":
            handle.seek(0)
    else:
        handle = io.open(path, "r", encoding="utf-8-sig", newline="")
    try:
        reader = csv.DictReader(handle)
        for index, raw in enumerate(reader, 1):
            if PY2:
                row = dict((to_text(key), to_text(value)) for key, value in raw.items())
            else:
                row = raw
            if to_text(row.get("enabled", "1")).strip().lower() in ("0", "false", "no", "n"):
                continue
            ip = to_text(row.get("ip", "")).strip()
            if not ip:
                raise ValueError("CSV 第 %d 行缺少 ip" % (index + 1))
            robots.append({
                "robot_id": to_text(row.get("robot_id") or "%02d" % index).strip(),
                "ip": ip,
                "port": int(row.get("port") or 9559),
                "notes": to_text(row.get("notes", "")),
            })
    finally:
        handle.close()
    return robots

def _robots_from_args(args):
    robots = []
    if args.inventory:
        robots.extend(_read_inventory(args.inventory))
    for index, ip in enumerate(args.ip or [], 1):
        robot_id = args.robot_id if len(args.ip or []) == 1 else None
        robots.append({
            "robot_id": robot_id or "%02d" % index,
            "ip": to_text(ip).strip(), "port": args.port, "notes": "",
        })
    return robots

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(decode_argv(argv))
    if args.list_tests:
        for test_id, label, _function, profiles in list_tests():
            console_write("%-16s %-24s [%s]" % (test_id, label, ",".join(profiles)))
        return 0
    try:
        config = load_config(args.config)
    except Exception as exc:
        console_write("配置文件读取失败：%s" % to_text(exc))
        return 2
    valid_ids = set(item[0] for item in list_tests())
    profile_ids = set(item[0] for item in list_tests(args.profile))
    only_ids = set(item.strip() for item in (args.only or "").split(",") if item.strip())
    skip_ids = set(item.strip() for item in (args.skip or "").split(",") if item.strip())
    unknown = sorted((only_ids | skip_ids) - valid_ids)
    if unknown:
        console_write("未知测试 ID：%s 请先运行 run.bat -ListTests" % ", ".join(unknown))
        return 2
    outside_profile = sorted(only_ids - profile_ids)
    if outside_profile:
        console_write("所选测试不属于 %s 配置：%s" % (args.profile, ", ".join(outside_profile)))
        return 2
    remaining = (only_ids or profile_ids) - skip_ids
    if not args.collect_logs and not args.log_dir:
        remaining.discard("logs")
    if not remaining:
        console_write("筛选后没有任何测试项目，已拒绝生成空报告")
        return 2
    try:
        robots = _robots_from_args(args)
    except Exception as exc:
        console_write("机器人清单读取失败：%s" % to_text(exc))
        return 2
    if not robots:
        parser.error("请提供 --ip 或 --inventory")
    if not 1 <= args.ssh_port <= 65535:
        console_write("SSH 端口必须在 1 到 65535 之间")
        return 2
    for robot in robots:
        if not robot["ip"] or not 1 <= robot["port"] <= 65535:
            console_write("机器人 %s 的地址为空或端口超出范围" % robot["robot_id"])
            return 2
    if args.interactive is None:
        args.interactive = args.profile in ("guided", "full")
    if args.allow_walk and not args.allow_motion:
        console_write("提示：--allow-walk 还需要 --allow-motion；行走项目将安全跳过")
    if args.allow_walk and args.assume_yes:
        console_write("拒绝启动：--allow-walk 不能与 --assume-yes 同时使用")
        return 2
    exit_code = 0
    reports = []
    try:
        import naoqi  # noqa: F401
    except ImportError as exc:
        console_write(
            "无法导入 pynaoqi：%s\n请使用项目的 run.ps1，它会自动定位现有 Python 2.7 和 SDK。" % to_text(exc)
        )
        return 4
    for robot in robots:
        try:
            payload, paths = run_robot(robot, config, args)
            reports.append(paths["html"])
            if payload["overall_status"] in ("FAIL", "ERROR"):
                exit_code = max(exit_code, 2)
            elif payload["overall_status"] in ("WARN", "SKIP"):
                exit_code = max(exit_code, 1)
            if payload.get("safety", {}).get("manual_intervention_required"):
                console_write(
                    "%s 的运动测试需要人工安全处置；为避免切换机器人时遗留危险状态，批次已停止" %
                    robot.get("robot_id"))
                break
        except KeyboardInterrupt:
            console_write("已由用户中断")
            return 130
        except Exception as exc:
            console_write("%s 检查启动失败：%s" % (robot.get("robot_id"), to_text(exc)))
            exit_code = max(exit_code, 3)
    console_write("本批次完成 报告：")
    for path in reports:
        console_write("  %s" % path)
    return exit_code
