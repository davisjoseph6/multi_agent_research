"""Repeatable, local-only SQLite writer-contention sweep for fictional A/B/C visits.

Run:
    python -m scripts.pilot_worker_count_sweep \
        --participants 30 --simulations 240 --workers 1,2,3,5 --repetitions 3 \
        > ~/ijcai_worker_count_sweep.json

This uses independent disposable SQLite databases, no real identities, no
network calls, and does not establish production throughput or safe enrollment.
"""
from __future__ import annotations

import argparse
import json
from statistics import median

from src.prototype.pilot_full_journey_rehearsal import run_full_journey_rehearsal


def parse_worker_counts(value: str) -> tuple[int, ...]:
    """Reject duplicate or invalid worker counts; keep command-line order."""
    try:
        result = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise ValueError("workers must be comma-separated integers") from error
    if len(result) < 2 or len(set(result)) != len(result) or any(
        isinstance(worker, bool) or not 1 <= worker <= 16 for worker in result
    ):
        raise ValueError("provide at least two distinct worker counts in 1..16")
    return result


def order_for_repetition(workers: tuple[int, ...], repetition: int) -> tuple[int, ...]:
    """Reverse on alternating repetitions to reduce fixed-order bias."""
    return workers if repetition % 2 == 0 else workers[::-1]


def _median(values: list[float]) -> float:
    return round(median(values), 3) if values else 0.0


def _run_entry(report: dict, repetition: int) -> dict:
    """Keep only aggregate fictional timings, no participant/action details."""
    phases = report["sqlite_phase_latency_ms"]
    return {
        "repetition": repetition + 1,
        "workers": report["workers"],
        "passed": report["result"] == "PASS" and not report["failures"],
        "failure_count": len(report["failures"]),
        "completed": report["completed_participants"],
        "completed_visits": report["completed_visits"],
        "action_calls": report["action_calls"],
        "elapsed_seconds": report["wall_seconds"],
        "actions_over_1000ms": report["actions_over_1000ms"],
        "action_p50_ms": report["latency_ms"]["p50"],
        "action_p95_ms": report["latency_ms"]["p95"],
        "action_p99_ms": report["latency_ms"]["p99"],
        "action_max_ms": report["latency_ms"]["max"],
        "sqlite_entry_p99_ms": phases["sqlite_begin_total_ms"]["p99"],
        "sqlite_body_p99_ms": phases["sqlite_body_total_ms"]["p99"],
        "sqlite_finalize_p99_ms": phases["sqlite_finalize_total_ms"]["p99"],
    }


MEASUREMENTS = (
    "elapsed_seconds", "actions_over_1000ms", "action_p50_ms",
    "action_p95_ms", "action_p99_ms", "action_max_ms",
    "sqlite_entry_p99_ms", "sqlite_body_p99_ms",
    "sqlite_finalize_p99_ms",
)


def summarize(entries: list[dict], counts: tuple[int, ...]) -> dict:
    """Median of per-run metrics; not a pooled percentile or confidence interval."""
    return {
        str(worker): {
            "run_count": sum(r["workers"] == worker for r in entries),
            "all_runs_passed": all(
                r["passed"] for r in entries if r["workers"] == worker
            ) and any(r["workers"] == worker for r in entries),
            "median_of_run_metrics": {
                metric: _median([
                    r[metric] for r in entries if r["workers"] == worker
                ])
                for metric in MEASUREMENTS
            },
        }
        for worker in counts
    }


def run_sweep(
    *, participants: int = 9, simulations: int = 41,
    workers: tuple[int, ...] = (1, 2, 3, 5), repetitions: int = 2,
) -> dict:
    if type(participants) is not int or not 3 <= participants <= 90 \
            or participants % 3:
        raise ValueError("participants must be a multiple of 3 between 3 and 90")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("simulations must be 41..240")
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ValueError("repetitions must be 1..10")
    if type(workers) is not tuple or len(workers) < 2 \
            or len(set(workers)) != len(workers) \
            or any(type(w) is not int or not 1 <= w <= 16 for w in workers):
        raise ValueError("workers must be a tuple of at least 2 distinct counts, 1..16")
    if len(workers) * repetitions > 48:
        raise ValueError("no more than 48 total runs in one sweep")

    runs = []
    for repetition in range(repetitions):
        for worker in order_for_repetition(workers, repetition):
            report = run_full_journey_rehearsal(
                participants=participants,
                workers=worker,
                simulations=simulations,
            )
            runs.append(_run_entry(report, repetition))

    all_passed = all(item["passed"] and item["completed"] == participants
                     and item["completed_visits"] == participants * 3
                     for item in runs)
    return {
        "kind": "OFFLINE_SYNTHETIC_SQLITE_WORKER_COUNT_SENSITIVITY_ONLY",
        "result": "PASS" if all_passed else "FAIL",
        "fictional_only": True,
        "human_enrollment_authorized": False,
        "external_https_load": False,
        "scientific_validation": False,
        "production_capacity_established": False,
        "latency_thresholds_approved": False,
        "journal_mode": "DELETE_default_no_WAL_change",
        "participants_per_run": participants,
        "simulations": simulations,
        "repetitions": repetitions,
        "worker_counts": list(workers),
        "order_policy": "alternating_forward_reverse",
        "runs": runs,
        "summary": summarize(runs, workers),
        "interpretation_limits": (
            "Median of independent synthetic run quantiles, not a pooled "
            "percentile or statistical confidence interval; entry includes "
            "connection/PRAGMAs/BEGIN and cannot isolate lock wait; "
            "no network, HTTP/TLS, browser, or live student load. "
            "Repeat on an idle system and independently validate before release."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=9)
    parser.add_argument("--simulations", type=int, default=41)
    parser.add_argument("--workers", default="1,2,3,5")
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    try:
        result = run_sweep(
            participants=args.participants,
            simulations=args.simulations,
            workers=parse_worker_counts(args.workers),
            repetitions=args.repetitions,
        )
    except ValueError as error:
        parser.exit(2, "INVALID OFFLINE SWEEP: " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if result["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
