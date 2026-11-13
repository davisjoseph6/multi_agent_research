"""Deterministic 3/4/7-day student inactivity policy.

A read-only decision engine for authorized researchers and the future verified
LIVE worker; no network, identity updates or recruitment take place here.
Scheduled gaps between the three study visits are NOT quiz abandonment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

PHASE_LABELS = {
    "PRETEST": {"en":"pre-test","fr":"pré-test"},
    "QUIZ":{"en":"learning quiz","fr":"quiz d’apprentissage"},
    "POSTTEST":{"en":"post-test","fr":"post-test"},
    "SURVEY":{"en":"fatigue questionnaire","fr":"questionnaire de fatigue"},
}
AUTO_AFTER=timedelta(days=3)
MANUAL_AFTER=timedelta(days=4)
EXPIRE_AFTER=timedelta(days=7)
SILENCE=timedelta(days=1)
WAITING={"WAITING_NEXT_SESSION","DONE"}


def evaluate_inactivity(*, now: datetime, last_active: datetime,
                        phase: str, session: int, status: str,
                        last_reminder: datetime | None = None,
                        automatic_enabled: bool = True,
                        manual_requested: bool = False,
                        locale: str = "en") -> dict:
    for value in (now,last_active,last_reminder):
        if value is not None and (not isinstance(value,datetime) or value.tzinfo is None):
            raise ValueError("timezone-aware timestamps required")
    if phase not in PHASE_LABELS and phase not in WAITING:
        raise ValueError("unknown study phase")
    if type(session) is not int or session not in (1,2,3):
        raise ValueError("session must be 1, 2, or 3")
    if locale not in ("en","fr") or type(automatic_enabled) is not bool:
        raise ValueError("valid locale and reminder policy required")
    if type(manual_requested) is not bool:
        raise ValueError("manual flag must be boolean")
    delta=now.astimezone(timezone.utc)-last_active.astimezone(timezone.utc)
    if delta<timedelta(0):
        raise ValueError("future last-activity timestamp")
    baseline=dict(send=False,expired=False,reason="none",stage=None,
                  idle_seconds=round(delta.total_seconds(),3))
    if status!="active" or phase in WAITING:
        baseline["reason"]="inactive_or_between_scheduled_visits"
        return baseline
    baseline["stage"]=PHASE_LABELS[phase][locale]
    if delta>=EXPIRE_AFTER:
        baseline.update(expired=True,reason="seven_day_session_inactivity")
        return baseline
    since_reminder=(
        now.astimezone(timezone.utc)-last_reminder.astimezone(timezone.utc)
        if last_reminder else None
    )
    if since_reminder is not None and since_reminder<timedelta(0):
        raise ValueError("future reminder timestamp")
    if (manual_requested and delta>=MANUAL_AFTER and
            (since_reminder is None or since_reminder>=SILENCE)):
        baseline.update(send=True,reason="manual_four_day_encouragement")
    elif (not manual_requested and automatic_enabled and delta>=AUTO_AFTER and
          (since_reminder is None or since_reminder>=AUTO_AFTER)):
        baseline.update(send=True,reason="automatic_three_day_encouragement")
    return baseline


def make_reminder_text(*, session: int, phase: str, language: str):
    stage=PHASE_LABELS[phase][language]
    if language=="fr":
        return (
            f"Votre séance {session} sur 3 est encore en cours, à l’étape « {stage} ». "
            "Vous pouvez reprendre à l’aide de votre lien privé. "
            "N’utilisez pas ce lien sur un appareil partagé."
        )
    return (
        f"Your session {session} of 3 is still in progress at the {stage} stage. "
        "You can resume using your private invitation link. "
        "Do not open that link on a shared device."
    )
