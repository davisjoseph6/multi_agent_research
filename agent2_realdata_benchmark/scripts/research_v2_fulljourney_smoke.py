"""Offline synthetic-only Research V2 lifecycle smoke (never recruit users).

Simulates a SINGLE learner through three distinct arms with 261 independent
question IDs and a question-anchored recovery, without pretending they are
reviewed, translated content. Also checks a private fictional reminder cycle.
There is no HTTP server, institutional contact, or email sending.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore
from src.prototype.research_v2_reminder_outbox import SyntheticReminderOutbox
from src.prototype.research_v2_proposal import (
    QUESTIONS_PER_ARM, TwoWrongRecovery, all_sequences,
)


T0 = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def run_smoke(root: Path, sequence: tuple[str, str, str] = ("A", "C", "B")) -> dict:
    """Three fictional periods, eight-concept-independent policy not simulated."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    crossover = FictionalCrossoverStore(root / "fictional_crossover.sqlite3")
    contacts = SyntheticReminderOutbox(root / "fictional_contact_outbox.sqlite3")
    learner = "SYN_CROSSOVER_F1"
    ref = "SYN_CONTACT_F1"
    crossover.enroll_fictional(learner, sequence)
    contacts.register(ref, "fictional@example.test", locale="fr", opted_in=True)
    contacts.pause(ref, T0)
    first, = contacts.reserve_due(T0 + timedelta(days=3))
    assert contacts.deliver_preview(first, T0 + timedelta(days=3))["preview_delivered"]
    assert not contacts.reserve_due(T0 + timedelta(days=5))
    second, = contacts.reserve_due(T0 + timedelta(days=6))
    assert contacts.deliver_preview(second, T0 + timedelta(days=6))["preview_delivered"]
    contacts.resume(ref, T0 + timedelta(days=6))
    assert contacts.reserve_due(T0 + timedelta(days=9)) == ()
    interventions = 0
    retries = 0
    for period, arm in enumerate(sequence):
        now = T0 + timedelta(days=7 + period)
        token = crossover.issue_token(learner, now)
        recovery = TwoWrongRecovery()
        for form, length in QUESTIONS_PER_ARM.items():
            for number in range(length):
                item_id = f"p{period}_{form}_{number}"
                wrong = arm == "A" and form == "practice" and number < 4
                result = crossover.record(
                    learner, token, request_id=f"req_{period}_{form}_{number}",
                    item_id=item_id, form=form, correct=not wrong, at=now,
                )
                assert result["accepted"] and result["counted"]
                if form == "practice":
                    triggered = recovery.observe_question(
                        arm=arm, stage="practice", correct=not wrong,
                    )
                    if triggered:
                        action = recovery.choose_recovery()
                        interventions += 1
                        if action == "DROP_2":
                            retry = crossover.record(
                                learner, token,
                                request_id=f"retry_{period}_{number:03d}",
                                item_id=item_id, form="practice", correct=True,
                                kind="DROP_2", at=now,
                            )
                            assert not retry["counted"]
                            retries += 1
                        recovery.acknowledge_recovery(action)
        finished = crossover.finish_period(learner, token, now)
        assert finished == period + 1
    progress = crossover.redacted_progress(learner)
    assert progress["finished"]
    assert interventions == 2
    assert retries == 1
    return {
        "synthetic_only": True,
        "human_enrollment_authorized": False,
        "real_email_sent": False,
        "sequence": list(sequence),
        "distinct_independent_questions": sum(QUESTIONS_PER_ARM.values()) * 3,
        "recovery_interventions_simulated": interventions,
        "instructional_drop2_retries": retries,
        "reminder_preview_count": 2,
        "completed_periods": progress["period_index"],
        "passed": True,
    }


def main() -> None:
    reports = []
    with TemporaryDirectory(prefix="ijcai_research_v2_fictional_") as temp:
        for i, order in enumerate(all_sequences()):
            reports.append(run_smoke(Path(temp) / str(i), order))
    print(json.dumps({
        "kind": "SYNTHETIC_THREE_PERIOD_LIFECYCLE_SMOKE",
        "six_sequences_passed": len(reports),
        "human_enrollment_authorized": False,
        "real_email_sent": False,
        "sample": reports[0],
    }, indent=2))


if __name__ == "__main__":
    main()
