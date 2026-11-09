"""Balanced-order, repeatable local-only SQLite journaling *sensitivity* study.

This runs the disposable fictional full three-visit synthetic workload with
both rollback DELETE and WAL journal modes. Repeat pairs alternate execution
order to reduce (not eliminate) order effects. No participant data, no HTTPS,
no live study database, and no permission to recruit students. A result of
SYNTHETIC_TESTS_PASSED never means production performance is acceptable.

From agent2_realdata_benchmark:
  python -m scripts.pilot_journal_pair_comparison \
    --participants 30 --workers 5 --simulations 240 --repetitions 3 \
    > "$HOME/ijcai_journal_compare_240.json"
"""
from __future__ import annotations

import argparse
import json
from statistics import median

from src.prototype.pilot_full_journey_rehearsal import run_full_journey_rehearsal

METRICS = ("p50", "p95", "p99", "max")


def compare_journal_modes(
    *, participants: int = 3, workers: int = 2,
    simulations: int = 41, repetitions: int = 1,
) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 6:
        raise ValueError("repetitions must be an integer from 1 through 6")
    if (type(participants) is not int
            or not 3 <= participants <= 90 or participants % 3
            or type(workers) is not int or not 1 <= workers <= 16
            or type(simulations) is not int or not 41 <= simulations <= 240):
        raise ValueError("invalid synthetic workload parameters")

    runs = []
    for pair in range(repetitions):
        order = ("delete", "wal") if pair % 2 == 0 else ("wal", "delete")
        for journal_mode in order:
            report = run_full_journey_rehearsal(
                participants=participants, workers=workers,
                simulations=simulations, journal_mode=journal_mode,
            )
            runs.append({
                "pair": pair + 1,
                "journal_mode": report["sqlite_journal_mode"],
                "result": report["result"],
                "completed_participants": report["completed_participants"],
                "completed_visits": report["completed_visits"],
                "failures": report["failures"],
                "latency_ms": report["latency_ms"],
                "sqlite_entry_latency_ms": report[
                    "sqlite_phase_latency_ms"
                ]["sqlite_begin_total_ms"],
                "actions_over_1000ms": report["actions_over_1000ms"],
                "wall_seconds": report["wall_seconds"],
            })
            if report["result"] != "PASS":
                # Fail closed; no further stress after a functional failure.
                return {
                    "result": "SYNTHETIC_FUNCTIONAL_FAILURE",
                    "runs": runs,
                    "human_enrollment_authorized": False,
                    "production_performance_approved": False,
                }
    summary = {}
    for mode in ("delete", "wal"):
        selected = [r for r in runs if r["journal_mode"] == mode]
        summary[mode] = {
            "pairs": len(selected),
            "action_latency_median_of_run_quantiles_ms": {
                k: round(median(x["latency_ms"][k] for x in selected), 3)
                for k in METRICS
            },
            "sqlite_entry_median_of_run_quantiles_ms": {
                k: round(
                    median(x["sqlite_entry_latency_ms"][k] for x in selected), 3
                )
                for k in METRICS
            },
            "median_actions_over_1000ms": median(
                x["actions_over_1000ms"] for x in selected
            ),
            "median_wall_seconds": round(
                median(x["wall_seconds"] for x in selected), 3
            ),
        }
    return {
        "kind": "PAIRED_ORDER_DELETE_VS_WAL_FULL_JOURNEY_SYNTHETIC_ONLY",
        "result": "SYNTHETIC_TESTS_PASSED",
        "participants": participants,
        "workers": workers,
        "planner_simulations": simulations,
        "repetitions": repetitions,
        "mode_order_alternates": True,
        "runs": runs,
        "summary": summary,
        "success_is_not_a_wal_speedup_claim": True,
        "not_repeated_identical_planner_randomness": True,
        "sqlite_wal_remains_single_writer": True,
        "not_external_https_load": True,
        "human_enrollment_authorized": False,
        "production_performance_approved": False,
        "approved_slo": False,
        "all_release_evidence_gates_pending": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=3)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--simulations", type=int, default=41)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    try:
        report = compare_journal_modes(
            participants=args.participants,
            workers=args.workers,
            simulations=args.simulations,
            repetitions=args.repetitions,
        )
    except ValueError as error:
        parser.exit(2, "INVALID SYNTHETIC COMPARISON: " + str(error) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(
        0 if report["result"] == "SYNTHETIC_TESTS_PASSED" else 2
    )


if __name__ == "__main__":
    main()
