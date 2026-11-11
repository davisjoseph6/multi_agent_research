"""Eight-concept live trace is built from stored scored observations only."""
from datetime import datetime, timezone
import pytest

from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore
from src.prototype.research_v2_proposal import ProposedStudyError
from src.prototype.study_v2 import CONCEPTS

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
REF = "SYN_CROSSOVER_F1"


def init(tmp_path):
    store = FictionalCrossoverStore(tmp_path / "fictional_crossover.sqlite3")
    store.enroll_fictional(REF, ("A", "B", "C"))
    return store, store.issue_token(REF, NOW)


def put(store, token, item, form, correct=True, concept=CONCEPTS[0]):
    return store.record(
        REF, token, request_id="answer_" + item,
        item_id=item, form=form, correct=correct, concept=concept, at=NOW,
    )


def test_mastery_is_per_learner_and_observed_scores_are_independent(tmp_path):
    store, token = init(tmp_path)
    empty = store.mastery_trace(REF, token, NOW)
    assert len(empty["points"]) == 1
    assert empty["independent_scores"] == {"pretest": None, "posttest": None}
    with pytest.raises(ProposedStudyError, match="token"):
        store.mastery_trace(REF, "invalid", NOW)
    for i in range(15):
        put(store, token, f"pre{i}", "pretest", concept=CONCEPTS[i % 8])
    partially = store.mastery_trace(REF, token, NOW)
    assert len(partially["points"]) == 16
    assert partially["independent_scores"]["pretest"] is None
    put(store, token, "pre15", "pretest", concept=CONCEPTS[7])
    after_pretest = store.mastery_trace(REF, token, NOW)
    assert after_pretest["independent_scores"]["pretest"] == 16
    pre_mastery = after_pretest["points"][-1]["mastery"][CONCEPTS[0]]
    put(store, token, "practice0", "practice", concept=CONCEPTS[0])
    practice = store.mastery_trace(REF, token, NOW)
    assert practice["points"][-1]["mastery"][CONCEPTS[0]] >= pre_mastery
    assert practice["independent_scores"]["posttest"] is None
    assert "email" not in str(practice).lower()
    assert not practice["human_enrollment_authorized"]


def test_missing_concept_metadata_fails_closed_instead_of_inventing_bkt(tmp_path):
    store, token = init(tmp_path)
    store.record(
        REF, token, request_id="first_unlabeled", item_id="pre_unknown",
        form="pretest", correct=True, at=NOW,
    )
    with pytest.raises(ProposedStudyError, match="trusted concept"):
        store.mastery_trace(REF, token, NOW)


def test_drop2_retry_is_not_added_to_live_mastery_evidence(tmp_path):
    store, token = init(tmp_path)
    for i in range(16):
        put(store, token, f"pre{i}", "pretest", concept=CONCEPTS[i % 8])
    put(store, token, "wrong0", "practice", False)
    put(store, token, "wrong1", "practice", False)
    assert store.pending_recovery(REF)["action"] == "CONCEPT_SUMMARY"
    store.acknowledge_recovery(
        REF, token, kind="CONCEPT_SUMMARY",
        request_id="ack_first", at=NOW,
    )
    store.decide_after_recovery(REF, token, decision="continue", at=NOW)
    put(store, token, "wrong2", "practice", False)
    put(store, token, "wrong3", "practice", False)
    before = store.mastery_trace(REF, token, NOW)
    assert store.pending_recovery(REF)["action"] == "DROP_2"
    store.record(
        REF, token, request_id="retry_drop2", item_id="wrong3",
        form="practice", correct=True, kind="DROP_2", at=NOW,
    )
    after = store.mastery_trace(REF, token, NOW)
    assert after["points"] == before["points"]
    assert after["independent_scores"] == before["independent_scores"]
    assert after["points"][-1]["answered"] == 20
