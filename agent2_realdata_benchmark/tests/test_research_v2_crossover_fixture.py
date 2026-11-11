"""Isolated SQLite rehearsal of synthetic V2 crossover invariants."""
from datetime import datetime, timedelta, timezone
import pytest

from src.prototype.research_v2_proposal import ProposedStudyError
from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore


T0 = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
REF = "SYN_CROSSOVER_F1"


def setup(tmp_path):
    path = tmp_path / "fictional_crossover.sqlite3"
    s = FictionalCrossoverStore(path)
    s.enroll_fictional(REF, ("A", "C", "B"))
    token = s.issue_token(REF, T0)
    return s, token, path


def answer(s, token, item_id, form, number, *, correct=True, kind="QUESTION", when=T0):
    return s.record(REF, token, request_id="fictional_" + str(number),
                    item_id=item_id, form=form, correct=correct,
                    kind=kind, at=when)


def test_order_no_repeats_and_three_periods_persist_across_processes(tmp_path):
    s, token, path = setup(tmp_path)
    with pytest.raises(ProposedStudyError, match="pretest"):
        answer(s, token, "early_p", "practice", "early")
    for period in range(3):
        if period:
            token = s.issue_token(REF, T0 + timedelta(days=period))
        for form, quantity in (("pretest", 16), ("practice", 55), ("posttest", 16)):
            for n in range(quantity):
                name = f"p{period}_{form}_{n}"
                answer(s, token, name, form, f"r{period}_{form}_{n}")
        s2 = FictionalCrossoverStore(path)
        assert s2.finish_period(REF, token, T0 + timedelta(days=period)) == period + 1
        with pytest.raises(ProposedStudyError):
            answer(s2, token, "stale", "practice", f"stale_{period}")
        s = s2
    progress = s.redacted_progress(REF)
    assert progress["finished"] and progress["period_index"] == 3
    with pytest.raises(ProposedStudyError):
        s.issue_token(REF, T0)


def test_immediate_drop2_only_once_after_incorrect_arm_a_practice(tmp_path):
    s, token, _ = setup(tmp_path)
    for i in range(16):
        answer(s, token, f"pre{i}", "pretest", f"pre_{i}")
    with pytest.raises(ProposedStudyError, match="latest wrong"):
        answer(s, token, "bad", "practice", "drop_0", kind="DROP_2")
    answer(s, token, "wrong0", "practice", "normal_0", correct=False)
    result = answer(s, token, "wrong0", "practice", "drop_1", kind="DROP_2")
    assert not result["counted"]
    with pytest.raises(ProposedStudyError, match="latest wrong"):
        answer(s, token, "wrong0", "practice", "drop_2", kind="DROP_2")
    with pytest.raises(ProposedStudyError, match="repeated"):
        answer(s, token, "wrong0", "practice", "normal_1", correct=False)


def test_retries_are_idempotent_but_changed_payload_is_rejected(tmp_path):
    s, token, _ = setup(tmp_path)
    x = answer(s, token, "pre1", "pretest", "first_001")
    assert x["accepted"] and not x["replayed"]
    y = answer(s, token, "pre1", "pretest", "first_001")
    assert y["replayed"]
    with pytest.raises(ProposedStudyError, match="changed"):
        answer(s, token, "pre2", "pretest", "first_001")
    assert s.redacted_progress(REF)["counts"]["pretest"] == 1


def test_pause_expiry_and_token_renewal_are_independent(tmp_path):
    s, token, _ = setup(tmp_path)
    s.pause(REF, token, T0 + timedelta(days=1))
    with pytest.raises(ProposedStudyError, match="paused"):
        answer(s, token, "pre0", "pretest", "while_pause",
               when=T0 + timedelta(days=2))
    after_original_expiry = T0 + timedelta(days=14, seconds=1)
    with pytest.raises(ProposedStudyError, match="renewal"):
        s.resume(REF, token, after_original_expiry)
    renewed = s.rotate_token(REF, T0 + timedelta(days=13),
                             contact_identity_verified=True)
    with pytest.raises(ProposedStudyError, match="renewal"):
        s.resume(REF, token, after_original_expiry)
    s.resume(REF, renewed, after_original_expiry)
    assert not s.redacted_progress(REF)["paused"]
    s.pause(REF, renewed, after_original_expiry)
    with pytest.raises(ProposedStudyError, match="interval"):
        s.resume(REF, renewed, T0 + timedelta(days=29, seconds=2))


def test_token_secrets_not_exposed_in_sanitized_progress(tmp_path):
    s, token, _ = setup(tmp_path)
    report = s.redacted_progress(REF)
    assert "token" not in report
    assert token not in str(report)
    with pytest.raises(ProposedStudyError, match="invalid"):
        answer(s, "wrong-token", "pre2", "pretest", "bad_auth")
