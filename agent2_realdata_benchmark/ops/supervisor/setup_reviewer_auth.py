"""Install independent /study/* reviewer Basic Auth without sharing operator access.

Run on VPS as root after reviewing the existing Caddyfile. This changes only
the known named matcher and adds one Caddy basic_auth block for /study/*.
It fails closed for unfamiliar layouts, validates Caddy, tests the new scoped
credentials over HTTPS, and restores the dated backup if any step fails.

The reviewer password never appears in argv, Git, server logs, or stdout.
No participant database or application service is modified.
"""
from __future__ import annotations

import base64
from getpass import getpass
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request

CADDY = Path("/etc/caddy/Caddyfile")
HOST = "https://demo.selfhealing-edu.fr"
USERNAME = "studyreviewer"
FRONTEND = "@frontend not path /api/rct/*"
STUDY = "@supervisorStudy path /study /study/*"
PROXY = "reverse_proxy @supervisorStudy 127.0.0.1:8788"
HASH = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z")


def render(source: str, credential_hash: str) -> str:
    """Pure exact-layout edit; reject anything that might change operator auth."""
    if not HASH.fullmatch(credential_hash):
        raise ValueError("Caddy bcrypt hash required")
    if "basic_auth @supervisorStudy" in source:
        raise ValueError("study reviewer auth exists; use reviewed rotation instead")
    if source.count(FRONTEND) != 1 or source.count(STUDY) != 1:
        raise ValueError("expected a single original frontend/study matcher")
    if (source.count("basic_auth @frontend {") != 1 or
            source.count(PROXY) != 1 or
            source.count("reverse_proxy 127.0.0.1:8077 {") != 1):
        raise ValueError("unexpected proxy or operator auth configuration")
    match_frontend = re.search(
        r"(?m)^([ \t]*)@frontend not path /api/rct/\*[ \t]*$", source
    )
    match_study = re.search(
        r"(?m)^([ \t]*)@supervisorStudy path /study /study/\*[ \t]*$", source
    )
    if not match_frontend or not match_study:
        raise ValueError("unsupported Caddyfile layout")
    # Crucially, the operator password must cease to match /study.
    source = source.replace(
        match_frontend.group(0),
        match_frontend.group(1) +
        "@frontend not path /api/rct/* /study /study/*",
        1,
    )
    # The study route is now protected by *only* this separate credential.
    indentation = match_study.group(1)
    block = (
        indentation + "basic_auth @supervisorStudy {\n"
        + indentation + "    " + USERNAME + " " + credential_hash + "\n"
        + indentation + "}\n"
    )
    source = source.replace(match_study.group(0) + "\n",
                            match_study.group(0) + "\n" + block, 1)
    if (source.count("basic_auth @supervisorStudy {") != 1 or
            source.count("basic_auth @frontend {") != 1):
        raise ValueError("unexpected authentication mutation")
    return source


def command(*argv: str, timeout: int = 25) -> None:
    subprocess.run(argv, check=True, timeout=timeout)


def status(path: str, username: str | None = None,
           password: str | None = None) -> int:
    headers = {}
    if username is not None and password is not None:
        token = base64.b64encode((username + ":" + password).encode()).decode()
        headers["Authorization"] = "Basic " + token
    request = urllib.request.Request(HOST + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def apply(path: Path = CADDY) -> None:
    if os.geteuid() != 0:
        raise PermissionError("run as root using sudo on the VPS")
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing non-symlink Caddyfile required")
    mode = path.stat()
    if not stat.S_ISREG(mode.st_mode):
        raise ValueError("Caddyfile must be a regular file")
    original = path.read_text(encoding="utf-8")
    # Fail before asking for secrets if the config cannot safely be changed.
    render(original, "$2a$14$" + "A" * 53)
    password = getpass("New STUDY-ONLY reviewer password (20+ characters): ")
    confirm = getpass("Repeat STUDY-ONLY reviewer password: ")
    if (not secrets.compare_digest(password, confirm)
            or len(password) < 20 or len(password) > 256
            or "\n" in password or "\r" in password):
        raise ValueError("password confirmation/length failed")
    hashed = subprocess.run(
        ["caddy", "hash-password", "--algorithm", "bcrypt"],
        input=password + "\n", text=True, capture_output=True, check=True,
        timeout=30,
    ).stdout.strip()
    new_config = render(original, hashed)
    backup = path.with_name(path.name + ".study-auth.bak." +
                            secrets.token_hex(6))
    temp_name = None
    changed = False
    try:
        shutil.copy2(path, backup)
        os.chown(backup, mode.st_uid, mode.st_gid)
        fd, temp_name = tempfile.mkstemp(prefix=".study-auth-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(new_config)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp_name, stat.S_IMODE(mode.st_mode))
        os.chown(temp_name, mode.st_uid, mode.st_gid)
        if path.read_text(encoding="utf-8") != original:
            raise RuntimeError("Caddyfile changed during preparation")
        os.replace(temp_name, path)
        temp_name = None
        changed = True
        command("caddy", "validate", "--config", str(path),
                "--adapter", "caddyfile")
        command("systemctl", "reload", "caddy")
        # A reviewer must get ONLY the study portal. The demo root stays
        # protected by the original operator credentials.
        checks = {
            "study without authentication": (status("/study/"), 401),
            "study with reviewer authentication": (
                status("/study/", USERNAME, password), 200),
            "operator root with reviewer authentication": (
                status("/", USERNAME, password), 401),
        }
        errors = [key for key, (got, expected) in checks.items()
                  if got != expected]
        if errors:
            raise RuntimeError("scoped auth acceptance failed: " + ", ".join(errors))
    except BaseException:
        if changed:
            # Preserve previous working Caddyfile and reload it.
            shutil.copy2(backup, path)
            os.chown(path, mode.st_uid, mode.st_gid)
            subprocess.run(["systemctl", "reload", "caddy"],
                           check=False, timeout=20)
        raise
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
    print("PASS: separate study-only Caddy authentication installed.")
    print("PASS: reviewer credentials access /study/ but not the operator root.")
    print("PASS: unauthenticated /study/ returns 401.")
    print("Operator password and 8077 service unchanged.")
    print("Retained rollback backup:", backup)
    print("Share reviewer username '" + USERNAME + "' and password privately.")


if __name__ == "__main__":
    apply()
