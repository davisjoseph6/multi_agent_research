"""PI-configured session reminders and missed-visit reconciliation.

Operational-only persistence: messages are queued in the private contacts
attachment, never in research events or client JSON. The caller supplies a
verified SMTP transport in approved LIVE mode; tests inject an inert sender.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import secrets
from zoneinfo import ZoneInfo

from .supervisor_synthetic_store import SupervisorSyntheticStore, SyntheticStudyError, iso


def reconcile(store: SupervisorSyntheticStore, *, at: datetime,
              grace_hours: int, send=None) -> dict:
    if not isinstance(store,SupervisorSyntheticStore) or not store.operational:
        raise TypeError("operational study database required")
    if type(grace_hours) is not int or not 0 <= grace_hours <= 72:
        raise ValueError("PI-approved grace hours must be explicit, 0..72")
    now=datetime.fromisoformat(iso(at))
    out=dict(reminders_queued=0,reminders_sent=0,delivery_failures=0,
             missed_once=0,removed_after_two_misses=0,
             real_email_sent=False,student_identifiers_in_report=False)
    with store._tx() as db:
        rows=db.execute(
            "SELECT s.learner_id,s.session_no,s.scheduled_for,p.missed_sessions "
            "FROM sessions s JOIN participants p USING(learner_id) "
            "WHERE s.status='scheduled' AND p.status='active' "
            "AND s.session_no IN (2,3)"
        ).fetchall()
        for row in rows:
            scheduled=datetime.fromisoformat(row["scheduled_for"])
            # Run hourly or more often. A missed scheduled run may send late
            # but never after the scheduled session begins.
            if scheduled-timedelta(days=1) <= now < scheduled:
                db.execute(
                    "INSERT OR IGNORE INTO pii.reminder_outbox "
                    "(learner_id,session_no,kind,status,created_at) "
                    "VALUES(?,?,'visit_reminder','pending',?)",
                    (row["learner_id"],row["session_no"],iso(at)),
                )
            if now > scheduled+timedelta(hours=grace_hours):
                count=row["missed_sessions"]+1
                ref=row["learner_id"]
                if count>=2:
                    db.execute(
                        "UPDATE participants SET missed_sessions=2,status='removed',"
                        "status_changed_at=? WHERE learner_id=?",(iso(at),ref),
                    )
                    db.execute(
                        "UPDATE sessions SET status='missed' "
                        "WHERE learner_id=? AND session_no=?",
                        (ref,row["session_no"]),
                    )
                    db.execute(
                        "UPDATE pii.contacts SET token_hash=? WHERE learner_id=?",
                        (sha256(secrets.token_bytes(48)).hexdigest(),ref),
                    )
                    db.execute("DELETE FROM pii.invitations WHERE learner_id=?",(ref,))
                    db.execute("DELETE FROM pii.reminder_outbox WHERE learner_id=?",(ref,))
                    db.execute("DELETE FROM operational_rendered WHERE learner_id=?",(ref,))
                    out["removed_after_two_misses"]+=1
                else:
                    revised=now+timedelta(days=2)
                    db.execute(
                        "UPDATE participants SET missed_sessions=1,status_changed_at=? "
                        "WHERE learner_id=?",(iso(at),ref),
                    )
                    db.execute(
                        "UPDATE sessions SET scheduled_for=?,status='scheduled' "
                        "WHERE learner_id=? AND session_no=?",
                        (iso(revised),ref,row["session_no"]),
                    )
                    out["missed_once"]+=1
        pending=db.execute(
            "SELECT o.learner_id,o.session_no,o.kind,s.scheduled_for,c.email "
            "FROM pii.reminder_outbox o "
            "JOIN participants p ON p.learner_id=o.learner_id "
            "JOIN sessions s ON s.learner_id=o.learner_id "
            "AND s.session_no=o.session_no "
            "JOIN pii.contacts c ON c.learner_id=o.learner_id "
            "WHERE o.status='pending' AND p.status='active' "
            "AND s.status='scheduled' AND s.scheduled_for>? "
            "ORDER BY o.created_at,o.learner_id",
            (iso(at),),
        ).fetchall()
    out["reminders_queued"]=len(pending)
    if send is None:
        return out
    for row in pending:
        ref=row["learner_id"]
        scheduled=datetime.fromisoformat(row["scheduled_for"])
        paris=scheduled.astimezone(ZoneInfo("Europe/Paris"))
        time_label=paris.strftime("%d/%m/%Y at %H:%M (Europe/Paris)")
        message=(
            f"Your study session {row['session_no']} is scheduled for "
            f"{time_label}. Please return using the private invitation "
            "link you received when joining the study. You may stop "
            "participating at any time through your private portal."
        )
        # A real mail server may have accepted a message immediately before
        # a crash. This at-least-once outbox cannot prove inbox delivery.
        try:
            send(row["email"],"Adaptive learning study session reminder",message)
        except Exception:
            with store._tx() as db:
                db.execute(
                    "UPDATE pii.reminder_outbox SET attempts=attempts+1 "
                    "WHERE learner_id=? AND session_no=? AND kind='visit_reminder'",
                    (ref,row["session_no"]),
                )
            out["delivery_failures"]+=1
            continue
        with store._tx() as db:
            db.execute(
                "UPDATE pii.reminder_outbox SET status='sent',"
                "sent_at=?,attempts=attempts+1 "
                "WHERE learner_id=? AND session_no=? AND kind='visit_reminder'",
                (iso(at),ref,row["session_no"]),
            )
        out["reminders_sent"]+=1
        out["real_email_sent"]=True
    return out
