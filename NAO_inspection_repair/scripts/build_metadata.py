# -*- coding: utf-8 -*-
"""
@ Project            : NAO Robot Inspection Toolbox
@ Description        : Check build tools and record release file digests
@ Author             : XCrane
"""
from __future__ import print_function, unicode_literals
import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_tools(project):
    import pkg_resources
    tools = {}
    for relative in ("packaging/requirements-bootstrap.lock", "requirements-build.txt"):
        with io.open(os.path.join(project, relative), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith(("#", "--")):
                    continue
                requirement = pkg_resources.Requirement.parse(line.split(" --hash=", 1)[0])
                if requirement.marker and not requirement.marker.evaluate():
                    continue
                installed = pkg_resources.get_distribution(requirement.project_name)
                if installed not in requirement:
                    raise RuntimeError("Build tool mismatch: %s; installed %s. Install the hash-locked requirements first." %
                                       (requirement, installed.version))
                tools[requirement.project_name] = installed.version
    return tools


def write_manifest(project, archive, tools=None, signing=None):
    archive = os.path.abspath(archive)
    digest = sha256(archive)
    checksum_path = archive + ".sha256"
    with io.open(checksum_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("%s  %s\n" % (digest, os.path.basename(archive)))
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=project, stderr=subprocess.PIPE).decode("ascii").strip()
        except (OSError, subprocess.CalledProcessError):
            commit = None
    record = {
        "schema_version": 1, "source_commit": commit,
        "platform": platform.platform(), "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "build_tools": tools if tools is not None else verify_tools(project),
        "signing": signing or "not-recorded",
        "artifact": {"name": os.path.basename(archive), "size": os.path.getsize(archive), "sha256": digest},
        "locks": dict((relative, sha256(os.path.join(project, relative))) for relative in (
            "requirements-build.txt", "packaging/requirements-bootstrap.lock", "packaging/build-inputs.json")),
    }
    verified = os.path.join(project, "build", "verified-inputs.json")
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.path.isfile(verified):
        with io.open(verified, encoding="utf-8") as handle:
            record["verified_inputs"] = json.load(handle)
        record["input_verification"] = "pinned-downloads"
    else:
        record["input_verification"] = "local-environment-not-vendor-verified"
    with io.open(archive + ".build.json", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description="Validate and record build provenance")
    parser.add_argument("--archive")
    parser.add_argument("--signing", default="not-recorded")
    args = parser.parse_args()
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools = verify_tools(project)
    if args.archive:
        write_manifest(project, args.archive, tools, args.signing)
    print("Hash-locked build tool versions verified")


if __name__ == "__main__":
    main()
