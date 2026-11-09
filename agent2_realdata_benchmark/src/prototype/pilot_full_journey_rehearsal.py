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
import sqlite3
from time import perf_counter
import tempfile
import uuid

from .pilot_concurrency_rehearsal import (
    START, STAFF_FIXTURE, _MeasuredSyntheticStore, _percentile,
)
from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from .study_v2 import RECOVERY_ACTIONS


def _fictional_three_visits(
    store: SyntheticThreeArmPilotStore, pid: str, arm: str,
) -> dict:
    times_ms: list[float] = []
    phase_samples: list[dict] = []
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
            store.begin_action_capture()
            t0 = perf_counter()
            offered = store.next_action(pid, at=at)
            next_done = perf_counter()
            kind = offered["action"]
            actions[kind] += 1
            stages[offered["stage"]] += 1
            assert offered["synthetic_only"]
            assert offered["draft_content_not_approved"]
            assert store.mark_rendered(pid, offered["action_id"], at=at)["accepted"]
            render_done = perf_counter()

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
            submit_done = perf_counter()
            assert result["accepted"] and not result["replayed"]
            acquired = store.finish_action_capture()
            if len(acquired) != 3:
                raise AssertionError(
                    "expected next/render/submit SQLite transaction timing samples"
                )
            total_ms = (submit_done - t0) * 1000.0
            times_ms.append(total_ms)
            phase_samples.append({
                "arm": arm,
                "visit": visit,
                "stage": offered["stage"],
                "action": kind,
                "action_roundtrip_ms": total_ms,
                "next_ms": (next_done - t0) * 1000.0,
                "render_ms": (render_done - next_done) * 1000.0,
                "submit_ms": (submit_done - render_done) * 1000.0,
                "sqlite_begin_next_ms": acquired[0],
                "sqlite_begin_render_ms": acquired[1],
                "sqlite_begin_submit_ms": acquired[2],
                "sqlite_begin_total_ms": sum(acquired),
            })

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
        "phase_samples": phase_samples,
    }


def run_full_journey_rehearsal(
    *, participants: int = 3, workers: int = 3, simulations: int = 41,
    journal_mode: str = "delete",
) -> dict:
    """Return JSON-safe summary; never expose participant IDs or use network."""
    if type(participants) is not int or not 3 <= participants <= 90 \
            or participants % 3:
        raise ValueError("participants must be a multiple of three, 3..90")
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be 1..16")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("POMCP simulations must be 41..240")
    if type(journal_mode) is not str or journal_mode not in ("delete", "wal"):
        raise ValueError("journal mode must be 'delete' or 'wal'")

    content = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
    with tempfile.TemporaryDirectory(prefix="ijcai-fictional-3visits-") as tmp:
        store = _MeasuredSyntheticStore(
            Path(tmp) / "synthetic_only.sqlite3",
            items_path=content / "items.csv",
            resources_path=content / "resources.csv",
            simulations=simulations,
        )
        # Experiment on a brand-new disposable, strictly fictional DB only.
        # PRAGMA journal_mode requires no open transactions. Do not modify
        # an existing operator-demo or human-study SQLite database.
        with sqlite3.connect(store.path, timeout=30) as setup_db:
            actual_journal = setup_db.execute(
                "PRAGMA journal_mode=" + journal_mode.upper()
            ).fetchone()[0].lower()
        if actual_journal != journal_mode:
            raise RuntimeError("SQLite did not enable the requested journal mode")
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
        samples = [
            value for record in outcomes for value in record["phase_samples"]
        ]
        phase_names = (
            "next_ms", "render_ms", "submit_ms",
            "sqlite_begin_next_ms", "sqlite_begin_render_ms",
            "sqlite_begin_submit_ms", "sqlite_begin_total_ms",
        )
        def metrics(values):
            return {
                "p50": round(_percentile(values, 50), 3),
                "p95": round(_percentile(values, 95), 3),
                "p99": round(_percentile(values, 99), 3),
                "max": round(max(values, default=0), 3),
            }

        phases = {
            key: metrics([sample[key] for sample in samples])
            for key in phase_names
        }
        arms = {
            arm: {
                "count": len(group),
                "roundtrip_ms": metrics([
                    sample["action_roundtrip_ms"] for sample in group
                ]),
                "over_250ms": sum(
                    sample["action_roundtrip_ms"] > 250 for sample in group
                ),
                "over_1000ms": sum(
                    sample["action_roundtrip_ms"] > 1000 for sample in group
                ),
            }
            for arm in "ABC"
            for group in ([sample for sample in samples
                           if sample["arm"] == arm],)
        }
        visits = {
            str(visit): {
                "count": len(group),
                "roundtrip_ms": metrics([
                    sample["action_roundtrip_ms"] for sample in group
                ]),
            }
            for visit in (1, 2, 3)
            for group in ([sample for sample in samples
                           if sample["visit"] == visit],)
        }
        slowest = sorted(
            samples, key=lambda value: value["action_roundtrip_ms"],
            reverse=True,
        )[:10]
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
            "sqlite_phase_latency_ms": phases,
            "per_arm_latency": arms,
            "per_visit_latency": visits,
            "actions_over_250ms": sum(
                item["action_roundtrip_ms"] > 250 for item in samples
            ),
            "actions_over_1000ms": sum(
                item["action_roundtrip_ms"] > 1000 for item in samples
            ),
            "slowest_10_actions": [
                {key: round(value, 3) if type(value) is float else value
                 for key, value in item.items()}
                for item in slowest
            ],
            "latency_scope": (
                "Only next/render/submit; excludes status, HTTP, TLS, "
                "browser, authentication, OS resource monitoring and replay"
            ),
            "sqlite_entry_timing_limitations": (
                "Includes connection, PRAGMAs and BEGIN IMMEDIATE acquisition;"
                " does not separately measure lock wait or planner CPU"
            ),
            "workers": workers,
            "planner_simulations": simulations,
            "sqlite_journal_mode": actual_journal,
            "experimental_storage_only": True,
            "sqlite_wal_not_a_multiwriter_database": True,
            "journal_mode_comparison_not_a_capacity_certificate": True,
            "failures": failures,
            "not_scientific_validation": True,
        }
