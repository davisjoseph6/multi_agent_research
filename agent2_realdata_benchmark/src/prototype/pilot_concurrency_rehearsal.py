"""Isolated synthetic first-visit parallel-load rehearsal: no public service.

This checks SQL write contention, idempotent action API semantics and per-arm
question/recovery budgets under concurrent *fictional* records. It is NOT
external HTTPS load testing, production-scale hosting certification, or
approval for research on people. All timestamps are artificial fixtures.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
import tempfile
import uuid

from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from .study_v2 import RECOVERY_ACTIONS

START = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
STAFF_FIXTURE = dict(offline_staff_authorized=True,
                     synthetic_release_authorized=True)


def _percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    a = sorted(values)
    at = percent / 100.0 * (len(a) - 1)
    low = int(at)
    high = min(low + 1, len(a) - 1)
    return a[low] * (1 - (at - low)) + a[high] * (at - low)


def _visit_one(store: SyntheticThreeArmPilotStore, pid: str, arm: str) -> dict:
    calls: list[float] = []
    kinds = Counter()
    for idx in range(50):  # 38 base + at most two recovery actions
        snapshot = store.snapshot(pid)
        if snapshot["stage"] == "awaiting_visit":
            break
        at = START + timedelta(seconds=idx + 1)
        t0 = perf_counter()
        action = store.next_action(pid, at=at)
        kinds[action["action"]] += 1
        assert store.mark_rendered(pid, action["action_id"], at=at)["accepted"]
        if action["action"] in ("QUESTION", "DROP_2"):
            response = {"choice_id": action["question"]["options"][0][0]}
        elif action["action"] == "MVAS":
            response = {
                "rating": 30 if action["stage"] == "mvas_pre" else 45
            }
        else:
            if action["action"] not in RECOVERY_ACTIONS:
                raise AssertionError("unexpected rehearsal action")
            response = {"status": "completed"}
        submission = store.submit(
            pid, action["action_id"], uuid.uuid4().hex, response, at=at,
        )
        if not submission["accepted"] or submission["replayed"]:
            raise AssertionError("response was not accepted exactly once")
        calls.append((perf_counter() - t0) * 1000.0)
    else:
        raise AssertionError("first fictional visit did not terminate")
    snapshot = store.snapshot(pid)
    scores = store.scores(pid)
    assert snapshot["stage"] == "awaiting_visit"
    assert snapshot["visits_finished"] == 1
    assert snapshot["unique_practice_used"] == 20
    assert scores["pretest"]["answered"] == 16
    assert scores["practice"]["answered"] == 20
    assert kinds["QUESTION"] == 36
    assert kinds["MVAS"] == 2
    assert sum(kinds[k] for k in RECOVERY_ACTIONS) <= 2
    if arm in "BC" and sum(kinds[k] for k in RECOVERY_ACTIONS):
        raise AssertionError("control arm received recovery intervention")
    assert snapshot["fatigue_deltas"][0] == 15
    return dict(arm=arm, action_calls_ms=calls,
                question_actions=kinds["QUESTION"],
                recovery_actions=sum(kinds[k] for k in RECOVERY_ACTIONS))


def run_synthetic_parallel_rehearsal(*, participants: int = 9, workers: int = 3,
                                     simulations: int = 41) -> dict:
    """Run a disposable, local SQLite rehearsal; never uses user study data."""
    if type(participants) is not int or participants < 3 \
            or participants > 120 or participants % 3 != 0:
        raise ValueError("participants must be a multiple of 3 between 3 and 120")
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("simulations must be between 41 and 240")
    root = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
    with tempfile.TemporaryDirectory(prefix="ijcai-fictional-parallel-") as directory:
        store = SyntheticThreeArmPilotStore(
            Path(directory) / "synthetic_only.sqlite3",
            items_path=root / "items.csv",
            resources_path=root / "resources.csv",
            simulations=simulations,
        )
        pids = []
        for i in range(participants):
            arm = "ABC"[i % 3]
            pid = store.new_synthetic_participant(arm=arm, at=START)
            store.start_supervised_visit(pid, visit=1, at=START, **STAFF_FIXTURE)
            pids.append((pid, arm))
        started = perf_counter()
        completed = []
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_arm = {
                pool.submit(_visit_one, store, pid, arm): arm
                for pid, arm in pids
            }
            for future in as_completed(future_to_arm):
                try:
                    completed.append(future.result())
                except Exception as error:  # report synthetic-only class, no PII
                    errors.append(type(error).__name__ + ": " + str(error)[:200])
        elapsed = perf_counter() - started
        durations = [
            t for result in completed for t in result["action_calls_ms"]
        ]
        allocations = dict(Counter(result["arm"] for result in completed))
        passed = (not errors and len(completed) == participants
                  and allocations == {arm: participants // 3 for arm in "ABC"})
        return {
            "kind": "LOCAL_SQLITE_SYNTHETIC_PARALLEL_NOT_PRODUCTION_LOAD",
            "result": "PASS" if passed else "FAIL",
            "human_enrollment_authorized": False,
            "external_https_test": False,
            "research_approval": False,
            "requested_fictional_participants": participants,
            "completed_fictional_participants": len(completed),
            "by_arm": allocations,
            "max_workers": workers,
            "pomcp_simulations": simulations,
            "total_completed_action_calls": len(durations),
            "elapsed_seconds": round(elapsed, 4),
            "action_roundtrip_ms": {
                "p50": round(_percentile(durations, 50), 3),
                "p95": round(_percentile(durations, 95), 3),
                "p99": round(_percentile(durations, 99), 3),
                "max": round(max(durations) if durations else 0, 3),
            },
            "failures": errors,
            "thresholds_pi_approved": False,
            "not_real_world_capacity_evidence": True,
        }
