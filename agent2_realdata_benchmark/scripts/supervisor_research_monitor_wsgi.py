"""Separate SSH-tunnel-only researcher dashboard; NOT a public /study/ route."""
from __future__ import annotations

import os
from pathlib import Path

from src.prototype.supervisor_research_monitor import make_monitor_app


def make_wsgi_app():
    root = Path(os.environ["SUPERVISOR_VPS_ROOT"])
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("existing private research storage required")
    encoded = os.environ.get("SUPERVISOR_ADMIN_PASSWORD_HASH", "")
    if not encoded:
        raise RuntimeError("separate researcher credential not configured")
    return make_monitor_app(
        root / "supervisor_operational_study.sqlite3",
        admin_password_hash=encoded,
    )
