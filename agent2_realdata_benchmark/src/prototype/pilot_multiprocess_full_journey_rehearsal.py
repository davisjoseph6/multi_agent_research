"""Disposable *full three-visit* A/B/C rehearsal across independent processes.

Each spawned Python process uses its OWN store object and, if FIFO is chosen,
its OWN Python Condition/ticket counter. They share one synthetic SQLite file.
Unlike the earlier single-row multi-process integrity probe, every fictional
participant completes the entire 16/55/16-question sequence, six proposed
fatigue responses, bounded Arm A resources, and exactly-once replay checks.

NO actual students, HTTP/HTTPS, authentication, consent, enrollment, real
calendar scheduling, approved content, deployment or production throughput.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter

from .pilot_concurrency_rehearsal import START, _MeasuredSyntheticStore, _percentile
from .pilot_full_journey_rehearsal import (
    _FIFOMeasuredSyntheticStore, _fictional_three_visits,
)


def _child_full_visits(
    database: str, content_directory: str, assignments: list[tuple[str, str]],
    writer_admission: str, threads: int, simulations: int, go, messages, index: int,
):
    """Multiprocessing.spawn target. Never include identifiers in output."""
    try:
        klass = (
            _FIFOMeasuredSyntheticStore
            if writer_admission == "fifo" else _MeasuredSyntheticStore
        )
        content = Path(content_directory)
        store = klass(
            Path(database),
            items_path=content / "items.csv",
            resources_path=content / "resources.csv",
            simulations=simulations,
        )
        messages.put({"kind": "ready", "worker": index})
        if not go.wait(30):
            raise TimeoutError("fictional process start gate not released")
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = {
                pool.submit(_fictional_three_visits, store, pid, arm): arm
                for pid, arm in assignments
            }
            completed = []
            for future in as_completed(futures):
                completed.append(future.result())
        messages.put({
            "kind": "complete",
            "worker": index,
            "records": [
                {
                    "arm": x["arm"],
                    "visits": x["visits"],
                    "pretest": x["pretest"],
                    "practice": x["practice"],
                    "posttest": x["posttest"],
                    "mvas": x["mvas"],
                    "recoveries": sum(x["recovery_by_visit"]),
                    "replays": x["replayed_requests_checked"],
                    "action_count": x["completed_action_calls"],
                    # No participant IDs, responses, sensitive logs or tokens.
                    "latencies_ms": x["action_latency_ms"],
                }
                for x in completed
            ],
        })
    except BaseException as exc:
        messages.put({
            "kind": "error",
            "worker": index,
            "error_type": type(exc).__name__,
        })


def _pct(values: list[float]) -> dict:
    return {
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
        "p99": round(_percentile(values, 99), 3),
        "max": round(max(values, default=0), 3),
    }


def run_multiprocess_full_journey(
    *, participants: int = 6, processes: int = 2,
    threads_per_process: int = 2, simulations: int = 41,
    writer_admission: str = "native",
) -> dict:
    """Return aggregate fictional evidence, with no persistent DB or network."""
    if type(processes) is not int or not 2 <= processes <= 4:
        raise ValueError("processes must be 2..4")
    if (type(participants) is not int or not 6 <= participants <= 90
            or participants % (3 * processes) != 0):
        raise ValueError(
            "participants must be 6..90 and a multiple of 3 * processes"
        )
    if (type(threads_per_process) is not int
            or not 1 <= threads_per_process <= 4):
        raise ValueError("threads per process must be 1..4")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("POMCP simulations must be 41..240")
    if type(writer_admission) is not str or writer_admission not in (
        "native", "fifo",
    ):
        raise ValueError("writer admission must be native or fifo")

    content = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
    ctx = get_context("spawn")
    started = perf_counter()
    results, failures = [], []

    with TemporaryDirectory(prefix="ijcai-fictional-multiprocess-") as tmp:
        database = Path(tmp) / "synthetic_only.sqlite3"
        parent = _MeasuredSyntheticStore(
            database,
            items_path=content / "items.csv",
            resources_path=content / "resources.csv",
            simulations=simulations,
        )
        assignments = [[] for _ in range(processes)]
        for block in range(participants // 3):
            worker_index = block % processes
            for arm in "ABC":
                pid = parent.new_synthetic_participant(arm=arm, at=START)
                assignments[worker_index].append((pid, arm))

        go, messages = ctx.Event(), ctx.Queue()
        children = [
            ctx.Process(
                target=_child_full_visits,
                args=(
                    str(database), str(content), assignments[index],
                    writer_admission, threads_per_process, simulations,
                    go, messages, index,
                ),
            )
            for index in range(processes)
        ]
        try:
            for process in children:
                process.start()
            ready = set()
            while len(ready) < processes:
                try:
                    message = messages.get(timeout=35)
                except Empty:
                    failures.append({"error_type": "ProcessStartTimeout"})
                    break
                if message.get("kind") != "ready":
                    failures.append({
                        "error_type": message.get("error_type", "InvalidProcessMessage")
                    })
                    break
                ready.add(message["worker"])
            if not failures:
                go.set()
                for _ in range(processes):
                    try:
                        message = messages.get(timeout=120)
                    except Empty:
                        failures.append({"error_type": "ProcessResultTimeout"})
                        break
                    if message.get("kind") == "complete":
                        results.extend(message["records"])
                    else:
                        failures.append({
                            "error_type": message.get("error_type", "InvalidProcessMessage")
                        })
                        break
            go.set()
            for process in children:
                process.join(timeout=10)
                if process.is_alive() or process.exitcode != 0:
                    failures.append({"error_type": "ProcessExitFailure"})
        finally:
            go.set()
            for process in children:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            messages.close()
            messages.join_thread()

        with sqlite3.connect(database, timeout=5) as conn:
            integrity_ok = conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0] == "ok"
            persisted_arm_counts = dict(conn.execute(
                "SELECT arm,COUNT(*) FROM pilot_three_arm_people GROUP BY arm"
            ).fetchall())
            persisted_answers = conn.execute(
                "SELECT COUNT(*) FROM pilot_requests"
            ).fetchone()[0]

    by_arm = Counter(item["arm"] for item in results)
    all_latencies = [
        value for item in results for value in item["latencies_ms"]
    ]
    actions = sum(item["action_count"] for item in results)
    recoveries = sum(item["recoveries"] for item in results)
    replays = sum(item["replays"] for item in results)

    passed = (
        not failures and len(results) == participants and
        by_arm == {arm: participants // 3 for arm in "ABC"} and
        persisted_arm_counts == dict(by_arm) and integrity_ok and
        sum(x["visits"] for x in results) == participants * 3 and
        all(x["pretest"] == 16 and x["practice"] == 55
            and x["posttest"] == 16 and x["mvas"] == 6
            and x["replays"] > 0 for x in results) and
        persisted_answers == actions and
        actions == participants * 93 + recoveries
    )
    return {
        "kind": "FULL_THREE_VISIT_CROSS_PROCESS_SYNTHETIC_SQLITE_ONLY",
        "result": "PASS" if passed else "FAIL",
        "fictional_only": True,
        "human_enrollment_authorized": False,
        "real_student_identity_or_consent": False,
        "external_https_load": False,
        "real_calendar_enforcement_test": False,
        "approved_latency_thresholds": False,
        "independent_security_accessibility_qa": False,
        "separate_store_per_process": True,
        "cross_process_fifo_coordination": False,
        "participants": participants,
        "processes": processes,
        "threads_per_process": threads_per_process,
        "planner_simulations": simulations,
        "writer_admission": writer_admission,
        "completed_by_arm": dict(by_arm),
        "completed_visits": sum(item["visits"] for item in results),
        "pretest_answers": sum(item["pretest"] for item in results),
        "practice_answers": sum(item["practice"] for item in results),
        "posttest_answers": sum(item["posttest"] for item in results),
        "mvas_responses": sum(item["mvas"] for item in results),
        "recovery_actions": recoveries,
        "replays_verified": replays,
        "action_calls": actions,
        "persisted_requests": persisted_answers,
        "sqlite_integrity_ok": integrity_ok,
        "action_latency_ms": _pct(all_latencies),
        "wall_seconds": round(perf_counter() - started, 3),
        "failures": failures,
        "not_production_capacity_certificate": True,
    }
