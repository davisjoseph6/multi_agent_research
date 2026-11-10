"""Read-only live HTTP acceptance for the SSH-only fictional pilot preview.

Runs from the VPS itself or from WSL through an SSH *loopback* tunnel.
NEVER connects to public URLs, submits questionnaire responses, creates
participants, starts visits or alters the study database.

  python -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766

The server must be the fictional-only preview; 200 on its HTML/assets and 403
on an untrusted POST are *expected*. This script also checks that proposed
enrollment and visit-start URLs do not exist.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

EXPECTED_HEADER = "X-Synthetic-Only"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_loopback_base(base: str) -> str:
    """Deny DNS, remote hosts, embedded credentials, URLs with paths/queries."""
    if type(base) is not str:
        raise ValueError("base must be a string")
    parsed = urlsplit(base)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("invalid preview port") from error
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or not 1024 <= (port or 0) <= 65535
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.netloc != f"127.0.0.1:{port}"):
        raise ValueError("only explicit http://127.0.0.1:<unprivileged-port> allowed")
    return f"http://127.0.0.1:{port}"


def _request(base, path, *, payload=None, nonce=None, include_origin=True):
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        if include_origin:
            headers["Origin"] = base
        if nonce is not None:
            headers["X-Preview-Nonce"] = nonce
    request = Request(
        base + path,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="GET" if payload is None else "POST",
    )
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read(65536)
    except HTTPError as error:
        try:
            body = error.read(65536)
        finally:
            error.close()
        return error.code, dict(error.headers), body


def run_acceptance(base: str = "http://127.0.0.1:8766") -> dict:
    """Return fail-closed metadata only; no IDs, secrets or raw responses."""
    base = validate_loopback_base(base)
    checks = {}
    failures = []

    def require(label, condition):
        checks[label] = bool(condition)
        if not condition:
            failures.append(label)

    try:
        status, headers, body = _request(base, "/")
        html = body.decode("utf-8", "replace")
        require("fictional_home_200", status == 200)
        require("fictional_banner", "FICTIONAL DATA ONLY" in html)
        require("synthetic_header", headers.get(EXPECTED_HEADER) == "1")
        require("no_store", "no-store" in headers.get("Cache-Control", ""))
        require("deny_frame", headers.get("X-Frame-Options") == "DENY")
        require("strict_csp", "default-src 'none'" in
                headers.get("Content-Security-Policy", ""))
        match = re.search(
            r'<meta name="preview-nonce" content="([a-zA-Z0-9_-]{32,128})">',
            html,
        )
        require("nonce_only_inside_private_page", match is not None)
        if match is None:
            return _final(checks, failures)
        nonce = match.group(1)

        for path, label in (
            ("/preview.js", "static_js_200"),
            ("/preview.css", "static_css_200"),
        ):
            code, h, _ = _request(base, path)
            require(label, code == 200 and h.get(EXPECTED_HEADER) == "1")

        code, _, _ = _request(
            base, "/preview/api/status",
            payload={"arm": "A"}, nonce=None,
        )
        require("missing_nonce_denied", code == 403)

        code, _, _ = _request(
            base, "/preview/api/status",
            payload={"arm": "A"}, nonce=nonce, include_origin=False,
        )
        require("missing_origin_denied", code == 403)

        for arm in ("A", "B", "C"):
            code, h, raw = _request(
                base, "/preview/api/status",
                payload={"arm": arm}, nonce=nonce,
            )
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                data = {}
            require(
                f"fictional_arm_{arm}_status",
                code == 200 and h.get(EXPECTED_HEADER) == "1" and
                data.get("arm") == arm and
                data.get("fictional_only") is True and
                data.get("human_enrollment_authorized") is False,
            )

        for path, label in (
            ("/preview/api/enroll", "enrollment_route_absent"),
            ("/preview/api/start", "visit_start_route_absent"),
            ("/api/rct/enroll", "human_enrollment_route_absent"),
        ):
            code, _, _ = _request(
                base, path, payload={"arm": "A"}, nonce=nonce,
            )
            require(label, code == 404)

    except (OSError, URLError, ValueError, UnicodeError) as error:
        # Avoid exporting exception messages containing paths or response data.
        failures.append(f"request_error_{type(error).__name__}")

    return _final(checks, failures)


def _final(checks, failures):
    return {
        "kind": "PRIVATE_LOOPBACK_FICTIONAL_HTTP_ACCEPTANCE_ONLY",
        "result": "PASS" if not failures else "FAIL",
        "checked": len(checks),
        "checks": checks,
        "failures": failures,
        "human_enrollment_authorized": False,
        "external_https_test": False,
        "no_responses_or_identifiers_exported": True,
        "not_security_or_production_certification": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8766")
    args = parser.parse_args()
    try:
        result = run_acceptance(args.base)
    except ValueError as error:
        parser.exit(2, "Refusing non-loopback target: " + str(error) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
