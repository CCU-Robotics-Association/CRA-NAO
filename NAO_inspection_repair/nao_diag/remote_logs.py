# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import os
import subprocess
import threading
from .compat import ensure_dir, to_text

REMOTE_LOGS = [
    ("naoqi-tail.log", "/var/log/naoqi/tail-naoqi.log"),
    ("hal-tail.log", "/var/log/hal/tail-hal.log"),
    ("lola-tail.log", "/var/log/lola/tail-lola.log"),
    ("firmware-tail.log", "/var/log/firmware/tail-firmware.log"),
]

def _decode(data):
    if data is None:
        return ""
    if not isinstance(data, bytes):
        return to_text(data)
    return data.decode("utf-8", "replace")

def _run_ssh(base_command, remote_command, timeout_seconds=45):
    command = list(base_command) + [remote_command]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=None,
    )
    result = {"stdout": b"", "stderr": b"", "error": None}

    def communicate():
        try:
            result["stdout"], result["stderr"] = process.communicate()
        except Exception as exc:
            result["error"] = exc
    worker = threading.Thread(target=communicate)
    worker.daemon = True
    worker.start()
    try:
        worker.join(float(timeout_seconds))
    except KeyboardInterrupt:
        try:
            process.terminate()
        except Exception:
            pass
        worker.join(2.0)
        if worker.is_alive():
            try:
                process.kill()
            except Exception:
                pass
            worker.join(2.0)
        raise
    timed_out = worker.is_alive()
    if timed_out:
        try:
            process.terminate()
        except Exception:
            pass
        worker.join(2.0)
        if worker.is_alive():
            try:
                process.kill()
            except Exception:
                pass
            worker.join(2.0)
    if result["error"]:
        raise result["error"]
    stderr_text = _decode(result["stderr"])
    if timed_out:
        stderr_text = (stderr_text + "\nSSH command timed out after %s seconds" % timeout_seconds).strip()
    return (-9 if timed_out else process.returncode), result["stdout"] or b"", stderr_text

def collect_remote_logs(ip, destination, user="nao", ssh_port=22, key_path=None,
                        line_count=3000, non_interactive=True, logger=None):
    ensure_dir(destination)
    line_count = min(10000, max(100, int(line_count)))
    target = "%s@%s" % (to_text(user), to_text(ip))
    known_hosts = os.path.abspath(os.path.join(destination, "known_hosts")).replace("\\", "/")
    command = [
        "ssh", "-T", "-p", str(int(ssh_port)),
        "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=%s" % known_hosts,
        "-o", "BatchMode=yes",
    ]
    if key_path:
        command += ["-i", os.path.abspath(key_path)]
    command.append(target)
    collected = []
    errors = []
    jobs = [("journal-current-boot.log", "journalctl -b --no-pager -n %d" % int(line_count))]
    for local_name, remote_path in REMOTE_LOGS:
        jobs.append((
            local_name,
            "if test -r %s; then tail -n %d %s; else exit 44; fi" % (
                remote_path, int(line_count), remote_path,
            ),
        ))
    for local_name, remote_command in jobs:
        if logger:
            logger.info("通过 SSH 读取 %s" % local_name)
        try:
            return_code, stdout, stderr = _run_ssh(command, remote_command)
        except OSError as exc:
            errors.append({"name": local_name, "error": to_text(exc)})
            break
        if return_code == 0 and stdout:
            path = os.path.join(destination, local_name)
            with open(path, "wb") as handle:
                handle.write(stdout)
            collected.append(path)
        else:
            errors.append({
                "name": local_name,
                "return_code": return_code,
                "error": stderr.strip()[-1000:],
            })
    return {"collected": collected, "errors": errors, "target": target}
