"""Independent synthetic SQLite concurrent-action and replay tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import sqlite3

from src.prototype.pilot_concurrency_rehearsal import (
    START, STAFF_FIXTURE, run_synthetic_parallel_rehearsal,
)
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"


def build(tmp_path):
    return SyntheticThreeArmPilotStore(
        tmp_path / "synthetic_only.sqlite3",
        items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv",
        simulations=41,
    )


def test_pending_question_is_singleton_under_simultaneous_next(tmp_path):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="B", at=START)
    store.start_supervised_visit(pid, visit=1, at=START, **STAFF_FIXTURE)
    at = START + timedelta(seconds=1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        offered = list(pool.map(lambda _: store.next_action(pid, at=at), range(16)))
    assert len({record["action_id"] for record in offered}) == 1
    assert all(record == offered[0] for record in offered)
    with sqlite3.connect(store.path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM pilot_actions WHERE pid=?", (pid,)
        ).fetchone()[0] == 1


def test_simultaneous_identical_submission_is_applied_once(tmp_path):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="A", at=START)
    store.start_supervised_visit(pid, visit=1, at=START, **STAFF_FIXTURE)
    at = START + timedelta(seconds=1)
    action = store.next_action(pid, at=at)
    store.mark_rendered(pid, action["action_id"], at=at)
    data = dict(choice_id=action["question"]["options"][0][0])
    with ThreadPoolExecutor(max_workers=8) as pool:
        submissions = list(pool.map(
            lambda _: store.submit(
                pid, action["action_id"], "SAME_CONCURRENT_REQUEST", data, at=at
            ), range(12)
        ))
    assert all(result["accepted"] for result in submissions)
    assert sum(result["replayed"] is False for result in submissions) == 1
    assert sum(result["replayed"] is True for result in submissions) == 11
    assert store.snapshot(pid)["index"] == 1
    with sqlite3.connect(store.path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM pilot_requests WHERE pid=?", (pid,)
        ).fetchone()[0] == 1


def test_parallel_first_visit_maintains_arm_isolation_and_reports_metrics():
    report = run_synthetic_parallel_rehearsal(
        participants=6, workers=3, simulations=41,
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["by_arm"] == {"A": 2, "B": 2, "C": 2}
    assert report["completed_fictional_participants"] == 6
    assert not report["human_enrollment_authorized"]
    assert not report["external_https_test"]
    assert not report["thresholds_pi_approved"]
    assert report["total_completed_action_calls"] >= 6 * 38
    assert report["action_roundtrip_ms"]["p95"] >= 0


def test_parallel_load_rejects_invalid_balancing_and_unbounded_workers():
    import pytest
    for invalid in (0, 1, 2, 7, 121, True):
        with pytest.raises(ValueError):
            run_synthetic_parallel_rehearsal(participants=invalid)
    for invalid in (0, 17, False):
        with pytest.raises(ValueError):
            run_synthetic_parallel_rehearsal(workers=invalid)
