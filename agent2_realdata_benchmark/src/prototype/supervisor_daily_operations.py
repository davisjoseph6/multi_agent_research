"""Offline daily reminder/missed-visit reconciliation — SYNTHETIC ONLY.

The PI must approve the definition of a missed session (grace interval)
before any real scheduler can be deployed. This code does not send emails.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
import re

from .supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError, iso,
)
from .supervisor_reminder_preview import (
    MemoryOnlySupervisorReminders, dry_run,
)


def reconcile_missed_fictional(
    store: SupervisorSyntheticStore, *, at: datetime, grace_hours: int,
) -> dict:
    """Flag sessions 2/3 only after an explicit fictional deadline.

    One miss reschedules two days after detection, preserving learner state.
    Two misses revoke the link without any reminder/confirmation email.
    """
    if type(store) is not SupervisorSyntheticStore:
        raise SyntheticStudyError("fictional supervisor store required")
    if type(grace_hours) is not int or not 0 <= grace_hours <= 72:
        raise SyntheticStudyError("explicit PI-approved grace-hour fixture required")
    now=datetime.fromisoformat(iso(at))
    updated=[]
    with store._tx() as db:
        rows=db.execute(
            "SELECT s.learner_id,s.session_no,s.scheduled_for,"
            "p.missed_sessions,c.email "
            "FROM sessions s JOIN participants p USING(learner_id) "
            "JOIN pii.contacts c USING(learner_id) "
            "WHERE s.status='scheduled' AND p.status='active' "
            "AND s.session_no IN (2,3) "
            "ORDER BY s.learner_id,s.session_no",
        ).fetchall()
        for row in rows:
            ref=row["learner_id"]
            if (not re.fullmatch(r"SYN_SUPERVISOR_P\d{3,8}",ref)
                    or not row["email"].lower().endswith(".test")):
                raise SyntheticStudyError("nonfictional study record refused")
            due=datetime.fromisoformat(row["scheduled_for"])+timedelta(
                hours=grace_hours)
            if now<=due:
                continue
            misses=row["missed_sessions"]+1
            if misses>=2:
                db.execute(
                    "UPDATE participants SET missed_sessions=2,status='removed',"
                    "status_changed_at=? WHERE learner_id=?",
                    (iso(at),ref),
                )
                db.execute(
                    "UPDATE sessions SET status='missed' "
                    "WHERE learner_id=? AND session_no=?",
                    (ref,row["session_no"]),
                )
                db.execute(
                    "UPDATE pii.contacts SET token_hash=? WHERE learner_id=?",
                    (hashlib.sha256(secrets.token_bytes(48)).hexdigest(),ref),
                )
                updated.append({"learner_id":ref,"misses":2,"removed":True})
            else:
                rescheduled=now+timedelta(days=2)
                db.execute(
                    "UPDATE participants SET missed_sessions=1,"
                    "status_changed_at=? WHERE learner_id=?",
                    (iso(at),ref),
                )
                db.execute(
                    "UPDATE sessions SET scheduled_for=?,status='scheduled' "
                    "WHERE learner_id=? AND session_no=?",
                    (iso(rescheduled),ref,row["session_no"]),
                )
                updated.append({
                    "learner_id":ref,"misses":1,"removed":False,
                    "rescheduled_for":iso(rescheduled),
                })
    return {"synthetic_only":True,"real_email_sent":False,
            "status_changes":updated}


def dry_run_daily(
    store: SupervisorSyntheticStore, *, at: datetime,
    grace_hours: int,
) -> dict:
    """Capture fake reminder notices and process synthetic missed sessions."""
    memory=MemoryOnlySupervisorReminders()
    reminders=dry_run(store,memory,at=at)
    missed=reconcile_missed_fictional(
        store,at=at,grace_hours=grace_hours,
    )
    return {"synthetic_only":True,"real_email_sent":False,
            "reminder_capture":reminders,"missed":missed}
