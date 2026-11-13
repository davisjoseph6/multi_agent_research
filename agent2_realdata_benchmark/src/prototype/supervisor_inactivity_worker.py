"""Private, auditable inactivity scan and one-shot email dispatch.

No network or participant state mutation in dry-run mode. A production worker
must pass live_verified=True after verifying the signed institutional release.
Unknown Microsoft Graph delivery outcomes are never automatically retried.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import secrets

from .supervisor_inactivity_policy import (
    evaluate_inactivity, make_reminder_text, AUTO_AFTER,
)
from .supervisor_recruitment import RecruitmentLedger, utc
from .supervisor_synthetic_store import SupervisorSyntheticStore, iso
from .supervisor_operational_intake import OperationalIntake


def reconcile_inactivity(
    store: SupervisorSyntheticStore, ledger: RecruitmentLedger, *,
    at: datetime, send=None, live_verified: bool = False,
    manual_ref: str | None = None,
) -> dict:
    """Apply in-progress quiz inactivity policy without touching waiting visits.

    In production, a successful send is Graph 202 *acceptance* only; in case of
    timeout we cannot safely distinguish accepted from unaccepted, so leave
    state 'uncertain' for an authorized human to reconcile in Sent Items.
    """
    if not isinstance(store,SupervisorSyntheticStore) or not store.operational:
        raise TypeError("operational study store required")
    if not isinstance(ledger,RecruitmentLedger):
        raise TypeError("private administration ledger required")
    if send is not None and live_verified is not True:
        raise ValueError("real email requires independently signed live release")
    if manual_ref is not None and (
        type(manual_ref) is not str or
        not manual_ref.startswith("STUDY_P") or len(manual_ref)>20
    ):
        raise ValueError("valid explicit learner reference required")
    report={"due":0,"accepted":0,"uncertain":0,"expired":0,
            "mail_sent":False,"contains_identifiers":False}
    auto=ledger.reminder_enabled()
    now=utc(at)
    tasks=[]
    with store._tx() as db:
        rows=db.execute(
            "SELECT p.learner_id,p.status,p.study_language,"
            "ls.session_no,ls.step,ls.updated_at,c.email "
            "FROM participants p JOIN learner_state ls USING(learner_id) "
            "JOIN pii.contacts c USING(learner_id) "
            "WHERE p.status='active' AND (? IS NULL OR p.learner_id=?) "
            "ORDER BY p.learner_id",(manual_ref,manual_ref),
        ).fetchall()
        for row in rows:
            ref=row["learner_id"]
            last=datetime.fromisoformat(row["updated_at"])
            prior=db.execute(
                "SELECT state,accepted_at FROM pii.inactivity_outbox "
                "WHERE learner_id=? AND activity_at=? "
                "ORDER BY at DESC LIMIT 1",(ref,row["updated_at"]),
            ).fetchone()
            # No blind retry of an unfinished or uncertain transport request.
            blocked=prior is not None and prior["state"]!="accepted"
            most_recent=(datetime.fromisoformat(prior["accepted_at"])
                         if prior and prior["accepted_at"] else None)
            decision=evaluate_inactivity(
                now=at,last_active=last,phase=row["step"],
                session=row["session_no"],status=row["status"],
                last_reminder=most_recent,
                automatic_enabled=auto,
                manual_requested=manual_ref is not None,
                locale=row["study_language"],
            )
            if decision["expired"]:
                if live_verified:
                    invitation=db.execute(
                        "SELECT * FROM pii.invitations WHERE learner_id=? "
                        "AND state='registered'",(ref,)
                    ).fetchone()
                    if invitation is not None:
                        strict=OperationalIntake(
                            store,programs=("prevalidated",),inactivity_days=7)
                        strict._enforce_idle_expiry(db,invitation,at=at)
                        report["expired"]+=1
                continue
            if not decision["send"] or blocked:
                continue
            kind="manual" if decision["reason"].startswith("manual_") else "automatic"
            elapsed=at-last
            slot=("day-"+str(elapsed.days//3) if kind=="automatic"
                  else utc(at)[:10])
            if db.execute(
                "SELECT 1 FROM pii.inactivity_outbox "
                "WHERE learner_id=? AND activity_at=? AND kind=? AND slot=?",
                (ref,row["updated_at"],kind,slot),
            ).fetchone():
                continue
            report["due"]+=1
            tasks.append(dict(ref=ref,activity_at=row["updated_at"],
                              kind=kind,slot=slot,email=row["email"],
                              session=row["session_no"],phase=row["step"],
                              language=row["study_language"]))
    if send is None:
        return report
    for job in tasks:
        with store._tx() as db:
            current=db.execute(
                "SELECT p.status,l.updated_at,l.step FROM participants p "
                "JOIN learner_state l USING(learner_id) WHERE p.learner_id=?",
                (job["ref"],)
            ).fetchone()
            if (current is None or current["status"]!="active"
                    or current["updated_at"]!=job["activity_at"]
                    or current["step"]!=job["phase"]):
                continue
            try:
                db.execute(
                    "INSERT INTO pii.inactivity_outbox"
                    "(learner_id,activity_at,kind,slot,state,at) "
                    "VALUES(?,?,?,?,'dispatching',?)",
                    (job["ref"],job["activity_at"],job["kind"],
                     job["slot"],now),
                )
            except __import__("sqlite3").IntegrityError:
                continue
        body=make_reminder_text(
            session=job["session"],phase=job["phase"],language=job["language"])
        subject=("Rappel : reprise de votre étude d’apprentissage" if
                 job["language"]=="fr" else "Reminder: resume your learning study")
        try:
            send(to=job["email"],subject=subject,body=body)
        except Exception:
            with store._tx() as db:
                db.execute(
                    "UPDATE pii.inactivity_outbox SET state='uncertain' "
                    "WHERE learner_id=? AND activity_at=? AND kind=? AND slot=?",
                    (job["ref"],job["activity_at"],job["kind"],job["slot"]),
                )
            report["uncertain"]+=1
            continue
        with store._tx() as db:
            db.execute(
                "UPDATE pii.inactivity_outbox SET state='accepted',accepted_at=? "
                "WHERE learner_id=? AND activity_at=? AND kind=? AND slot=?",
                (now,job["ref"],job["activity_at"],job["kind"],job["slot"]),
            )
        report["accepted"]+=1
        report["mail_sent"]=True
    return report
