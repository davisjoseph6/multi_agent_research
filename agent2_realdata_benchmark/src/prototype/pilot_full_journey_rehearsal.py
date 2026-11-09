"""Disposable parallel THREE-VISIT fictional A/B/C end-to-end rehearsal.

Not a production load test, not human enrollment, not a scientifically
validated intervention, and not an approval of the draft 95 items/32 resources
or proposed digital fatigue instrument.

All participants are random SYN_PILOT_* records in one temporary local
SQLite database, destroyed before return. Study visit timestamps are
virtual and supervisor flags are fixtures. No HTTP or external VPS requests.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from time import perf_counter
import tempfile
import uuid

from .pilot_concurrency_rehearsal import START, STAFF_FIXTURE, _percentile
from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from .study_v2 import RECOVERY_ACTIONS


def _fictional_three_visits(
    store: SyntheticThreeArmPilotStore, pid: str, arm: str,
) -> dict:
    times_ms: list[float] = []
    actions = Counter()
    stages = Counter()
    replay_checks = 0
    recovery_by_visit = []

    for visit in (1, 2, 3):
        # 4 days between visit starts, leaving >=72 and <=120 hours
        # between finish of prior session and start of this session.
        start = START + timedelta(days=4 * (visit - 1))
        store.start_supervised_visit(pid, visit=visit, at=start, **STAFF_FIXTURE)
        recoveries = 0

        for step in range(64):
            before = store.snapshot(pid)
            if before["stage"] in ("awaiting_visit", "complete"):
                break

            at = start + timedelta(minutes=step + 1)
            t0 = perf_counter()
            offered = store.next_action(pid, at=at)
            kind = offered["action"]
            actions[kind] += 1
            stages[offered["stage"]] += 1
            assert offered["synthetic_only"]
            assert offered["draft_content_not_approved"]
            assert store.mark_rendered(pid, offered["action_id"], at=at)["accepted"]

            if kind in ("QUESTION", "DROP_2"):
                answer = {"choice_id": offered["question"]["options"][0][0]}
            elif kind == "MVAS":
                answer = {
                    "rating": 30 if offered["stage"] == "mvas_pre" else 45,
                }
            elif kind in RECOVERY_ACTIONS:
                answer = {"status": "completed"}
            else:
                raise AssertionError("unexpected synthetic action")

            request_id = uuid.uuid4().hex
            result = store.submit(
                pid, offered["action_id"], request_id, answer, at=at,
            )
            assert result["accepted"] and not result["replayed"]
            times_ms.append((perf_counter() - t0) * 1000.0)

            if kind in RECOVERY_ACTIONS:
                recoveries += 1
            if step % 7 == 0:
                replay = store.submit(
                    pid, offered["action_id"], request_id, answer, at=at,
                )
                assert replay["accepted"] and replay["replayed"]
                replay_checks += 1
        else:
            raise AssertionError("fictional visit failed to terminate")

        state = store.snapshot(pid)
        assert state["session"] == visit
        assert state["visits_finished"] == visit
        assert state["stage"] == ("complete" if visit == 3 else "awaiting_visit")
        assert recoveries <= 2
        if arm in ("B", "C"):
            assert recoveries == 0
        recovery_by_visit.append(recoveries)

    state = store.snapshot(pid)
    scores = store.scores(pid)
    assert scores["pretest"]["answered"] == 16
    assert scores["practice"]["answered"] == 55
    assert scores["posttest"]["answered"] == 16
    assert state["unique_practice_used"] == 55
    assert state["fatigue_deltas"] == (15, 15, 15)
    assert stages["mvas_pre"] == stages["mvas_post"] == 3
    assert state["visits_started"] == state["visits_finished"] == 3
    assert actions["QUESTION"] == 87
    assert actions["MVAS"] == 6
    assert sum(recovery_by_visit) <= 6
    assert state["recovery_completed"] == sum(recovery_by_visit)

    return {
        "arm": arm,
        "visits": 3,
        "pretest": scores["pretest"]["answered"],
        "practice": scores["practice"]["answered"],
        "posttest": scores["posttest"]["answered"],
        "mvas": actions["MVAS"],
        "recovery_by_visit": recovery_by_visit,
        "completed_action_calls": len(times_ms),
        "replayed_requests_checked": replay_checks,
        "action_latency_ms": times_ms,
    }


def run_full_journey_rehearsal(
    *, participants: int = 3, workers: int = 3, simulations: int = 41,
) -> dict:
    """Return JSON-safe summary; never expose participant IDs or use network."""
    if type(participants) is not int or not 3 <= participants <= 90 \
            or participants % 3:
        raise ValueError("participants must be a multiple of three, 3..90")
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be 1..16")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("POMCP simulations must be 41..240")

    content = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
    with tempfile.TemporaryDirectory(prefix="ijcai-fictional-3visits-") as tmp:
        store = SyntheticThreeArmPilotStore(
            Path(tmp) / "synthetic_only.sqlite3",
            items_path=content / "items.csv",
            resources_path=content / "resources.csv",
            simulations=simulations,
        )
        people = [
            (store.new_synthetic_participant(arm=arm, at=START), arm)
            for _ in range(participants // 3)
            for arm in "ABC"
        ]

        started = perf_counter()
        outcomes, failures = [], []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {
                pool.submit(_fictional_three_visits, store, pid, arm): arm
                for pid, arm in people
            }
            for future in as_completed(pending):
                try:
                    outcomes.append(future.result())
                except Exception as error:
                    # Never print synthetic participant IDs or raw responses.
                    failures.append({
                        "arm": pending[future],
                        "error_type": type(error).__name__,
                        "message": str(error)[:160],
                    })
        elapsed = perf_counter() - started

        by_arm = dict(Counter(record["arm"] for record in outcomes))
        latencies = [
            value for record in outcomes
            for value in record["action_latency_ms"]
        ]
        passed = (
            not failures and len(outcomes) == participants
            and by_arm == {arm: participants // 3 for arm in "ABC"}
        )
        return {
            "kind": "DISPOSABLE_THREE_VISIT_SYNTHETIC_SQLITE_ONLY",
            "result": "PASS" if passed else "FAIL",
            "fictional_only": True,
            "human_enrollment_authorized": False,
            "independent_research_qa": False,
            "external_https_load": False,
            "approved_latency_thresholds": False,
            "real_world_calendar_test": False,
            "requires_content_mvas_ethics_pi_approvals": True,
            "requested_participants": participants,
            "completed_participants": len(outcomes),
            "completed_by_arm": by_arm,
            "completed_visits": sum(x["visits"] for x in outcomes),
            "pretest_answers": sum(x["pretest"] for x in outcomes),
            "unique_practice_answers": sum(x["practice"] for x in outcomes),
            "posttest_answers": sum(x["posttest"] for x in outcomes),
            "mvas_responses": sum(x["mvas"] for x in outcomes),
            "recovery_actions": sum(
                sum(x["recovery_by_visit"]) for x in outcomes
            ),
            "replayed_requests_verified": sum(
                x["replayed_requests_checked"] for x in outcomes
            ),
            "action_calls": len(latencies),
            "latency_ms": {
                "p50": round(_percentile(latencies, 50), 3),
                "p95": round(_percentile(latencies, 95), 3),
                "p99": round(_percentile(latencies, 99), 3),
                "max": round(max(latencies) if latencies else 0, 3),
            },
            "wall_seconds": round(elapsed, 3),
            "workers": workers,
            "planner_simulations": simulations,
            "failures": failures,
            "not_scientific_validation": True,
        }
