# -*- coding: utf-8 -*-
"""
@ Project            : NAO Robot Inspection Toolbox
@ Description        : Verify pinned build downloads before installation
@ Author             : XCrane
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener


ALLOWED_HOSTS = {"www.python.org", "repo.anaconda.com", "community-static.aldebaran.com"}


def check_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or
            parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Build input URL must use an approved HTTPS origin")


class VerifiedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        check_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input(item):
    check_url(item["url"])
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", item["filename"]):
        raise ValueError("Invalid build input filename")
    if not re.match(r"^[0-9a-f]{64}$", item["sha256"]):
        raise ValueError("A pinned SHA256 is required")
    if type(item["size"]) is not int or item["size"] <= 0:
        raise ValueError("A positive pinned file size is required")


def verify_file(path, item):
    size = path.stat().st_size
    if size != item["size"]:
        raise ValueError("Build input size mismatch: %s; expected %s, received %s" %
                         (item["filename"], item["size"], size))
    digest = file_digest(path)
    if digest != item["sha256"]:
        raise ValueError("Build input SHA256 mismatch: %s; expected %s, received %s" %
                         (item["filename"], item["sha256"], digest))


def fetch(item, destination):
    validate_input(item)
    target = destination / item["filename"]
    if target.is_symlink():
        raise ValueError("Build input cache cannot contain symlinks")
    if target.exists():
        verify_file(target, item)
        return target
    descriptor, temporary = tempfile.mkstemp(prefix=".download-", dir=str(destination))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            opener = build_opener(VerifiedRedirect())
            with opener.open(item["url"], timeout=120) as response:
                check_url(response.geturl())
                length = response.headers.get("Content-Length")
                if length is not None and int(length) != item["size"]:
                    raise ValueError("Unexpected build input size")
                received = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > item["size"]:
                        raise ValueError("Build input exceeds pinned size")
                    handle.write(chunk)
        verify_file(Path(temporary), item)
        os.replace(temporary, str(target))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def main():
    parser = argparse.ArgumentParser(description="Fetch and verify native build inputs")
    parser.add_argument("--platform", choices=("linux", "macos"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    manifest_path = project / "packaging" / "build-inputs.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest["platforms"][args.platform]
    for item in items:
        validate_input(item)
    destination = Path(args.output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for item in items:
        fetch(item, destination)
        print("SHA256 verified: " + item["filename"], flush=True)
    record = {"platform": args.platform, "manifest_sha256": file_digest(manifest_path),
              "inputs": items}
    build = project / "build"
    build.mkdir(exist_ok=True)
    (build / "verified-inputs.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
