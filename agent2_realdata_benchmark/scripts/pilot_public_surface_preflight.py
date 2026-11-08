"""Noninvasive public HTTPS checks for the FICTIONAL OPERATOR DEMO only.

No credentials or participant invitation codes required.
Does not constitute independent penetration testing or WCAG review.

Run from local WSL/another network:
python -m scripts.pilot_public_surface_preflight

Hardcoded approved test hostname; no arbitrary URL or load generation.
"""
from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = "https://demo.selfhealing-edu.fr"
TIMEOUT = 12


def request_status(path, *, method="GET"):
    request = Request(
        URL + path,
        method=method,
        headers={"User-Agent": "IJCAI-fictional-preflight/1.0"},
    )
    try:
        with urlopen(request, context=ssl.create_default_context(),
                     timeout=TIMEOUT) as response:
            return response.status, dict(response.headers)
    except HTTPError as exc:
        return exc.code, dict(exc.headers)


def main():
    checks = [
        ("Unauthenticated homepage requires operator auth", "/", "GET", 401),
        ("Unauthenticated JS requires operator auth", "/app.js", "GET", 401),
        ("Unauthenticated CSS requires operator auth", "/app.css", "GET", 401),
        ("HTTP enrollment remains blocked", "/api/rct/enroll", "POST", 403),
    ]
    outcomes = []
    for label, path, method, expected in checks:
        try:
            status, headers = request_status(path, method=method)
            passed = status == expected
            if path == "/":
                passed &= "basic" in headers.get("WWW-Authenticate", "").lower()
            if path == "/api/rct/enroll":
                passed &= "no-store" in headers.get("Cache-Control", "")
            outcomes.append({
                "check": label, "passed": bool(passed),
                "status": status, "expected": expected,
            })
        except (OSError, URLError, ssl.SSLError) as exc:
            outcomes.append({
                "check": label, "passed": False,
                "error_type": type(exc).__name__,
            })
    report = {
        "kind": "FICTIONAL_OPERATOR_DEMO_PUBLIC_SURFACE_ONLY",
        "host": URL,
        "independent_pentest": False,
        "load_or_browser_test": False,
        "all_passed": all(x["passed"] for x in outcomes),
        "checks": outcomes,
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
