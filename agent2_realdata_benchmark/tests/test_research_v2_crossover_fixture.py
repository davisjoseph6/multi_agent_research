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


def test_two_wrong_mandatory_recovery_and_drop2_only_on_second_trigger(tmp_path):
    s, token, _ = setup(tmp_path)
    for i in range(16):
        answer(s, token, f"pre{i}", "pretest", f"pre_{i}")
    with pytest.raises(ProposedStudyError, match="second consecutive"):
        answer(s, token, "bad", "practice", "drop_0", kind="DROP_2")
    answer(s, token, "wrong0", "practice", "normal_0", correct=False)
    with pytest.raises(ProposedStudyError, match="second consecutive"):
        answer(s, token, "wrong0", "practice", "drop_1", kind="DROP_2")
    second = answer(s, token, "wrong1", "practice", "normal_1", correct=False)
    assert second["recovery_required"] == "CONCEPT_SUMMARY"
    assert s.pending_recovery(REF)["target_item_id"] == "wrong1"
    with pytest.raises(ProposedStudyError, match="recovery must complete"):
        answer(s, token, "next", "practice", "normal_2")
    ack = s.acknowledge_recovery(REF, token, kind="CONCEPT_SUMMARY",
                                 request_id="resource_001", at=T0)
    assert ack["accepted"] and not ack["counted"]
    assert s.acknowledge_recovery(REF, token, kind="CONCEPT_SUMMARY",
                                  request_id="resource_001", at=T0)["replayed"]
    with pytest.raises(ProposedStudyError, match="continue or pause"):
        answer(s, token, "next", "practice", "normal_2")
    s.decide_after_recovery(REF, token, decision="continue", at=T0)
    answer(s, token, "wrong2", "practice", "normal_2", correct=False)
    assert answer(s, token, "wrong3", "practice", "normal_3",
                  correct=False)["recovery_required"] == "DROP_2"
    result = answer(s, token, "wrong3", "practice", "drop_2", kind="DROP_2")
    assert not result["counted"]
    s.decide_after_recovery(REF, token, decision="continue", at=T0)
    with pytest.raises(ProposedStudyError, match="second consecutive"):
        answer(s, token, "wrong3", "practice", "drop_3", kind="DROP_2")
    with pytest.raises(ProposedStudyError, match="repeated"):
        answer(s, token, "wrong3", "practice", "normal_4", correct=False)


def test_final_practice_error_requires_recovery_before_posttest(tmp_path):
    s, token, path = setup(tmp_path)
    for i in range(16):
        answer(s, token, f"pre{i}", "pretest", f"pre_{i}")
    for i in range(53):
        answer(s, token, f"p{i}", "practice", f"p_{i}")
    answer(s, token, "p53", "practice", "p_53", correct=False)
    assert answer(s, token, "p54", "practice", "p_54",
                  correct=False)["recovery_required"] == "CONCEPT_SUMMARY"
    restarted = FictionalCrossoverStore(path)
    assert restarted.pending_recovery(REF)["action"] == "CONCEPT_SUMMARY"
    with pytest.raises(ProposedStudyError, match="recovery must complete"):
        answer(restarted, token, "post0", "posttest", "post_0")
    restarted.acknowledge_recovery(REF, token, kind="CONCEPT_SUMMARY",
                                   request_id="ack_final", at=T0)
    with pytest.raises(ProposedStudyError, match="continue or pause"):
        answer(restarted, token, "post0", "posttest", "post_0")
    restarted.decide_after_recovery(REF, token, decision="continue", at=T0)
    for i in range(16):
        answer(restarted, token, f"post{i}", "posttest", f"post_{i}")
    assert restarted.finish_period(REF, token, T0) == 1


def test_correct_answer_breaks_wrong_streak_even_after_restart(tmp_path):
    s, token, path = setup(tmp_path)
    for i in range(16):
        answer(s, token, f"pre{i}", "pretest", f"pre_{i}")
    answer(s, token, "q0", "practice", "q_0", correct=False)
    answer(s, token, "q1", "practice", "q_1", correct=True)
    answer(s, token, "q2", "practice", "q_2", correct=False)
    assert s.pending_recovery(REF)["action"] is None
    s = FictionalCrossoverStore(path)
    answer(s, token, "q3", "practice", "q_3", correct=False)
    assert s.pending_recovery(REF)["action"] == "CONCEPT_SUMMARY"
    s.pause(REF, token, T0)
    with pytest.raises(ProposedStudyError, match="paused"):
        s.acknowledge_recovery(REF, token, kind="CONCEPT_SUMMARY",
                               request_id="ack_paused", at=T0)
    s.resume(REF, token, T0 + timedelta(hours=1))
    assert s.pending_recovery(REF)["action"] == "CONCEPT_SUMMARY"



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
