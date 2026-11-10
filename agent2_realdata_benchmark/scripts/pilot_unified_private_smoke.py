"""Read-only localhost HTTP acceptance for the unified *fictional* browser.

Never sends participant identities, responses, consent, or enrollment data.
Only GET assets and POST fictional status and intentionally invalid requests.
The tool refuses anything except an explicit localhost HTTP URL.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class FictionalSmokeFailure(AssertionError):
    pass


def _request(base: str, path: str, *,
             nonce: str | None = None,
             body: dict | None = None,
             origin: str | None = None,
             status_expected: int = 200):
    headers = {"Cache-Control": "no-store"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        if nonce is not None:
            headers["X-Preview-Nonce"] = nonce
        if origin is not None:
            headers["Origin"] = origin
    request = Request(base + path, data=data, headers=headers,
                      method="POST" if data is not None else "GET")
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        status = response.status
        result_headers = dict(response.headers.items())
        payload = response.read(100_000)
    if status != status_expected:
        raise FictionalSmokeFailure(
            "fictional HTTP acceptance unexpected status " + str(status)
            + " on " + path,
        )
    return result_headers, payload


def run_smoke(base: str = "http://127.0.0.1:8767") -> dict:
    parsed = urlparse(base)
    if (parsed.scheme != "http" or parsed.hostname not in
            ("127.0.0.1", "localhost")
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.port is None or not 1024 <= parsed.port <= 65535
            or base.rstrip("/") !=
            "http://" + parsed.netloc):
        raise FictionalSmokeFailure("only explicit localhost HTTP ports permitted")
    base = base.rstrip("/")
    checks: dict[str, bool] = {}
    headers, html = _request(base, "/")
    document = html.decode("utf-8")
    checks["fictional_html"] = "SYNTHETIC-ONLY" in document
    checks["fixture_selector"] = 'id="fixture-select"' in document
    checks["synthetic_header"] = headers.get("X-Synthetic-Only") == "1"
    checks["no_store"] = headers.get("Cache-Control") == "no-store"
    checks["deny_frames"] = headers.get("X-Frame-Options") == "DENY"
    checks["strict_csp"] = (
        "default-src 'none'" in headers.get("Content-Security-Policy", "")
    )
    checks["no_robots"] = "noindex" in headers.get("X-Robots-Tag", "")
    nonce_match = re.search(
        r'<meta name="preview-nonce" content="([a-zA-Z0-9_-]{32,128})">',
        document,
    )
    checks["private_nonce"] = nonce_match is not None
    if nonce_match is None:
        raise FictionalSmokeFailure("private fictional nonce absent")
    nonce = nonce_match.group(1)
    for suffix in ("/unified.js", "/unified.css"):
        asset_headers, data = _request(base, suffix)
        checks["asset_" + suffix.rsplit(".", 1)[-1]] = (
            bool(data) and asset_headers.get("X-Synthetic-Only") == "1"
        )
    for fixture in ("F1", "F2", "F3"):
        _, payload = _request(
            base, "/unified/api/status",
            body={"fixture": fixture}, nonce=nonce, origin=base,
        )
        state = json.loads(payload)
        checks["fictional_" + fixture] = (
            state.get("fixture") == fixture
            and state.get("synthetic_only") is True
            and state.get("human_enrollment_authorized") is False
            and not any(key in state for key in
                        ("pid", "arm", "token", "assignment", "private_invitation"))
        )
    _request(base, "/unified/api/status", body={"fixture": "F1"},
             origin=base, status_expected=403)
    checks["missing_nonce_denied"] = True
    _request(base, "/unified/api/status",
             body={"fixture": "F1"}, nonce=nonce, status_expected=403)
    checks["missing_origin_denied"] = True
    _request(base, "/unified/api/status",
             body={"fixture": "F1", "arm": "A"}, nonce=nonce, origin=base,
             status_expected=409)
    checks["arm_override_denied"] = True
    for path in ("/unified/api/enroll", "/unified/api/start",
                 "/unified/api/consent", "/unified/api/withdraw"):
        _request(base, path, body={"fixture": "F1"},
                 nonce=nonce, origin=base, status_expected=404)
    checks["human_routes_absent"] = True
    _request(base, "/admin", status_expected=404)
    checks["admin_absent"] = True
    if not all(checks.values()):
        raise FictionalSmokeFailure(
            "fictional HTTP acceptance failed: "
            + ",".join(k for k, v in checks.items() if not v)
        )
    return {
        "kind": "PRIVATE_UNIFIED_FICTIONAL_HTTP_ACCEPTANCE",
        "result": "PASS",
        "checked": len(checks),
        "checks": checks,
        "human_enrollment_authorized": False,
        "external_https_test": False,
        "real_browser_accessibility_test": False,
        "production_security_certification": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8767")
    args = parser.parse_args()
    try:
        result = run_smoke(args.base)
    except Exception as error:
        print(json.dumps({
            "kind": "PRIVATE_UNIFIED_FICTIONAL_HTTP_ACCEPTANCE",
            "result": "FAIL",
            "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
