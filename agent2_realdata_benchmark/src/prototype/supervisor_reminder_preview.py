"""24-hour-before-session reminders — dry run only, NEVER sends email.

Matches participant_scenarios.docx and data_to_save.docx; does not reuse the
superseded three-day-dropout crossover notification policy. The caller must
be a privileged local fictional operator, never a public HTTP endpoint.
This module contains no SMTP, API provider, network requests or credentials.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re

from .supervisor_synthetic_store import SupervisorSyntheticStore, SyntheticStudyError, iso


def _due(row, now: datetime) -> bool:
    if row["status"] != "scheduled" or row["participant_status"] != "active":
        return False
    scheduled = datetime.fromisoformat(row["scheduled_for"])
    return scheduled - timedelta(hours=24) <= now < scheduled


def due_fictional_session_reminders(
    study: SupervisorSyntheticStore, *, at: datetime,
) -> tuple[dict, ...]:
    """Preview only, with .test recipients; no actual email transport."""
    if not isinstance(study, SupervisorSyntheticStore):
        raise TypeError("isolated supervisor synthetic store required")
    now = datetime.fromisoformat(iso(at))
    result = []
    with study._tx() as db:
        rows = db.execute(
            "SELECT s.learner_id,s.session_no,s.scheduled_for,s.status,"
            "p.status AS participant_status,c.email,c.reminders_sent "
            "FROM sessions s JOIN participants p USING(learner_id) "
            "JOIN pii.contacts c USING(learner_id) "
            "WHERE s.session_no IN (2,3) ORDER BY s.learner_id,s.session_no"
        ).fetchall()
        for row in rows:
            if not _due(row, now):
                continue
            if not isinstance(row["email"], str) or not re.fullmatch(
                r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.test",
                row["email"], flags=re.I,
            ):
                raise SyntheticStudyError("nonfictional recipient rejected")
            history = json.loads(row["reminders_sent"])
            claim = f"session_{row['session_no']}:{row['scheduled_for']}"
            if any(entry["key"] == claim for entry in history):
                continue
            result.append({
                "learner_id": row["learner_id"],
                "session_no": row["session_no"],
                "scheduled_for": row["scheduled_for"],
                "recipient": row["email"],
                "subject": "Fictional study session reminder",
                "message": (
                    "FICTIONAL ONLY: Your study session is scheduled "
                    "within the next 24 hours."
                ),
                "key": claim, "synthetic_only": True,
            })
    return tuple(result)


def acknowledge_fictional_reminder(
    study: SupervisorSyntheticStore, preview: dict, *, at: datetime,
) -> bool:
    """A successful MEMORY-ONLY delivery acknowledgment is persisted once.

    No real email provider is supported. Enrollment identifiers remain
    synthetic. On repeated calls return False, never append duplicate.
    """
    now = datetime.fromisoformat(iso(at))
    if (type(preview) is not dict or preview.get("synthetic_only") is not True
            or not re.fullmatch(
                r"SYN_SUPERVISOR_P\d{3,8}",
                str(preview.get("learner_id", "")),
            )
            or type(preview.get("session_no")) is not int
            or preview["session_no"] not in (2,3)):
        raise SyntheticStudyError("fictional delivery acknowledgment required")
    with study._tx() as db:
        row = db.execute(
            "SELECT s.learner_id,s.session_no,s.scheduled_for,s.status,"
            "p.status AS participant_status,c.email,c.reminders_sent "
            "FROM sessions s JOIN participants p USING(learner_id) "
            "JOIN pii.contacts c USING(learner_id) "
            "WHERE s.learner_id=? AND s.session_no=?",
            (preview["learner_id"], preview["session_no"]),
        ).fetchone()
        if row is None or not _due(row, now):
            raise SyntheticStudyError("fictional session reminder not currently due")
        key = f"session_{row['session_no']}:{row['scheduled_for']}"
        if (preview.get("key") != key
                or preview.get("recipient") != row["email"]):
            raise SyntheticStudyError("stale or tampered fictional reminder")
        entries = json.loads(row["reminders_sent"])
        if any(entry["key"] == key for entry in entries):
            return False
        entries.append({
            "key":key,
            "preview_acknowledged_at":iso(at),
            "transport":"MEMORY_ONLY_NO_REAL_EMAIL",
        })
        db.execute(
            "UPDATE pii.contacts SET reminders_sent=? WHERE learner_id=?",
            (json.dumps(entries,sort_keys=True),row["learner_id"]),
        )
    return True


class MemoryOnlySupervisorReminders:
    """Deliberately cannot send to a real email service."""

    def __init__(self):
        self.captured = {}
    def capture(self, preview: dict) -> bool:
        if (not preview.get("synthetic_only") or
                not preview.get("recipient","").lower().endswith(".test")):
            raise SyntheticStudyError("real transport or recipient refused")
        key = preview["learner_id"] + ":" + preview["key"]
        if key in self.captured:
            return False
        self.captured[key] = dict(preview)
        return True


def dry_run(study: SupervisorSyntheticStore, transport: MemoryOnlySupervisorReminders,
            *, at: datetime) -> dict:
    if type(transport) is not MemoryOnlySupervisorReminders:
        raise SyntheticStudyError("memory-only notifier required")
    claimed = due_fictional_session_reminders(study,at=at)
    completed = 0
    for preview in claimed:
        if transport.capture(preview):
            completed += acknowledge_fictional_reminder(study,preview,at=at)
    return {"synthetic_only":True,"real_email_sent":False,
            "captured_and_logged":completed,"due":len(claimed)}
