"""Separate Caddy Basic Auth realms for the existing operator and study portals.

Both authentication blocks currently default to realm="restricted", despite
different username/password databases. Browser credential caching can therefore
send the wrong credentials to an otherwise healthy service.

This is an on-VPS, root-only, deliberately narrow Caddyfile edit. It neither
creates nor replaces a password/hash, never touches the study/PII databases or
application workers, and rolls back if the config or HTTP acceptance fails.
"""
from __future__ import annotations

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

CADDY=Path("/etc/caddy/Caddyfile")
HOST="https://demo.selfhealing-edu.fr"
REVIEWER="StudyReview"
OPERATOR="OperatorDemo"
MATCHERS=(
    "@supervisorStudy path /study /study/*",
    "@frontend not path /api/rct/* /study /study/*",
)
EXPECTED=(
    "reverse_proxy @supervisorStudy 127.0.0.1:8788",
    "reverse_proxy 127.0.0.1:8077",
)


def render(source: str) -> str:
    """Return an idempotently isolated config, rejecting ambiguous layouts."""
    for expected in MATCHERS:
        # A prefix match is insufficient: a modified matcher could silently
        # include /admin/* while still containing the trusted substring.
        pattern=r"(?m)^[ \\t]*"+re.escape(expected)+r"[ \\t]*$"
        if len(re.findall(pattern,source))!=1:
            raise ValueError("unknown or duplicated Caddy path matcher")
    for expected in EXPECTED:
        pattern=r"(?m)^[ \\t]*"+re.escape(expected)+r"[ \\t]*\\{[ \\t]*$"
        if len(re.findall(pattern,source))!=1:
            raise ValueError("unknown or duplicated Caddy upstream")
    if source.count("basic_auth @supervisorStudy")!=1:
        raise ValueError("expected exactly one study reviewer auth block")
    if source.count("basic_auth @frontend")!=1:
        raise ValueError("expected exactly one operator auth block")

    replacements=(
        ("@supervisorStudy",REVIEWER),
        ("@frontend",OPERATOR),
    )
    updated=source
    for matcher,realm in replacements:
        expression=(r"(?m)^([ \t]*)basic_auth "+re.escape(matcher)
                    +r"(?: bcrypt ("+re.escape(realm)+r"))?[ \t]*\{[ \t]*$")
        matches=list(re.finditer(expression,updated))
        if len(matches)!=1:
            raise ValueError("unsupported Basic Auth scheme or existing realm")
        match=matches[0]
        replacement=match.group(1)+"basic_auth "+matcher+" bcrypt "+realm+" {"
        updated=updated[:match.start()]+replacement+updated[match.end():]

    # Check both scoped blocks remain unique and neither grant access to the
    # other application. No user record, hash, or upstream can be changed.
    if updated.count("basic_auth @supervisorStudy bcrypt StudyReview {")!=1:
        raise ValueError("study reviewer auth was not isolated")
    if updated.count("basic_auth @frontend bcrypt OperatorDemo {")!=1:
        raise ValueError("operator auth was not isolated")
    return updated


def challenge(path: str) -> tuple[int,str]:
    req=urllib.request.Request(HOST+path,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=12) as response:
            return response.status,response.headers.get("WWW-Authenticate","")
    except urllib.error.HTTPError as error:
        return error.code,error.headers.get("WWW-Authenticate","")


def validate_http() -> None:
    checks={
        "/":'Basic realm="OperatorDemo"',
        "/study/":'Basic realm="StudyReview"',
        "/study/app.js":'Basic realm="StudyReview"',
        "/study/app.css":'Basic realm="StudyReview"',
    }
    failures=[]
    for path,expected in checks.items():
        code,header=challenge(path)
        if code!=401 or header!=expected:
            failures.append(path)
    if failures:
        raise RuntimeError("separate authentication acceptance failed at: "
                           +", ".join(failures))


def apply(path: Path=CADDY) -> None:
    if os.geteuid()!=0:
        raise PermissionError("run as root on the VPS")
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing regular Caddyfile required")
    file_info=path.stat()
    if not stat.S_ISREG(file_info.st_mode):
        raise ValueError("regular Caddyfile required")
    before=path.read_text(encoding="utf-8")
    after=render(before)
    if after==before:
        validate_http()
        print("PASS: independent operator/study realms already configured")
        return

    backup=path.with_name(path.name+".separate-realms.bak."+secrets.token_hex(6))
    temporary=None
    replaced=False
    try:
        shutil.copy2(path,backup)
        os.chown(backup,file_info.st_uid,file_info.st_gid)
        fd,temporary=tempfile.mkstemp(prefix=".caddy-realms-",dir=path.parent)
        with os.fdopen(fd,"w",encoding="utf-8") as output:
            output.write(after)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary,stat.S_IMODE(file_info.st_mode))
        os.chown(temporary,file_info.st_uid,file_info.st_gid)
        subprocess.run(["caddy","validate","--config",str(temporary),
                        "--adapter","caddyfile"],
                       check=True,timeout=20)
        if path.read_text(encoding="utf-8")!=before:
            raise RuntimeError("Caddy configuration changed concurrently")
        os.replace(temporary,path)
        temporary=None
        replaced=True
        subprocess.run(["systemctl","reload","caddy"],check=True,timeout=20)
        validate_http()
    except BaseException:
        if replaced:
            shutil.copy2(backup,path)
            os.chown(path,file_info.st_uid,file_info.st_gid)
            subprocess.run(["systemctl","reload","caddy"],
                           check=False,timeout=20)
        raise
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)

    print("PASS: StudyReview and OperatorDemo browser realms are distinct")
    print("PASS: 401 protected operator root, study root, JS and CSS")
    print("PASS: existing usernames, password hashes and proxies unchanged")
    print("PASS: original operator demo and study database untouched")
    print("Rollback backup:",backup)
    print("Next: use a private browser and confirm each login separately.")


if __name__=="__main__":
    apply()
