"""Compare native SQLite vs process-local FIFO admission, SYNTHETIC ONLY.

The experiment runs COMPLETE fictional three-visit A/B/C journeys on fresh,
private temporary SQLite databases, in balanced alternating orders. It is not
an operational deployment, not a valid human-study enrollment engine, and not
a license to alter the demo VPS or any existing data.

Example, from agent2_realdata_benchmark:
  python -m scripts.pilot_writer_admission_pair_comparison \
    --participants 30 --workers 5 --simulations 240 --repetitions 3 \
    > "$HOME/ijcai_fifo_pair_comparison.json"
"""
from __future__ import annotations

import argparse
import json
from statistics import median

from src.prototype.pilot_full_journey_rehearsal import run_full_journey_rehearsal

METRICS = ("p50", "p95", "p99", "max")
MODES = ("native", "fifo")


def compare_writer_admission(*, participants: int = 3, workers: int = 2,
                             simulations: int = 41,
                             repetitions: int = 1) -> dict:
    if (type(repetitions) is not int or not 1 <= repetitions <= 6
            or type(participants) is not int
            or participants < 3 or participants > 90 or participants % 3
            or type(workers) is not int or not 1 <= workers <= 16
            or type(simulations) is not int or not 41 <= simulations <= 240):
        raise ValueError("invalid synthetic paired comparison configuration")

    runs = []
    for pair in range(repetitions):
        order = MODES if pair % 2 == 0 else tuple(reversed(MODES))
        for mode in order:
            report = run_full_journey_rehearsal(
                participants=participants, workers=workers,
                simulations=simulations, writer_admission=mode,
            )
            run = {
                "pair": pair + 1,
                "writer_admission": mode,
                "result": report["result"],
                "failures": report["failures"],
                "completed_participants": report["completed_participants"],
                "completed_by_arm": report["completed_by_arm"],
                "completed_visits": report["completed_visits"],
                "pretest_answers": report["pretest_answers"],
                "unique_practice_answers": report["unique_practice_answers"],
                "posttest_answers": report["posttest_answers"],
                "mvas_responses": report["mvas_responses"],
                "replayed_requests_verified": report["replayed_requests_verified"],
                "latency_ms": report["latency_ms"],
                "per_arm_latency": report["per_arm_latency"],
                "sqlite_entry_latency_ms": report[
                    "sqlite_phase_latency_ms"
                ]["sqlite_begin_total_ms"],
                "sqlite_body_latency_ms": report[
                    "sqlite_phase_latency_ms"
                ]["sqlite_body_total_ms"],
                "sqlite_finalize_latency_ms": report[
                    "sqlite_phase_latency_ms"
                ]["sqlite_finalize_total_ms"],
                "fifo_wait_latency_ms": report[
                    "sqlite_phase_latency_ms"
                ]["writer_queue_wait_total_ms"],
                "actions_over_1000ms": report["actions_over_1000ms"],
                "wall_seconds": report["wall_seconds"],
            }
            runs.append(run)
            if report["result"] != "PASS":
                return {
                    "result": "SYNTHETIC_FUNCTIONAL_FAILURE",
                    "runs": runs,
                    "human_enrollment_authorized": False,
                    "production_performance_approved": False,
                }

    summary = {}
    for mode in MODES:
        runs_for_mode = [x for x in runs if x["writer_admission"] == mode]
        summary[mode] = {
            "paired_runs": len(runs_for_mode),
            "median_of_run_action_quantiles_ms": {
                key: round(median(r["latency_ms"][key] for r in runs_for_mode), 3)
                for key in METRICS
            },
            "median_of_run_sqlite_entry_quantiles_ms": {
                key: round(median(
                    r["sqlite_entry_latency_ms"][key] for r in runs_for_mode
                ), 3)
                for key in METRICS
            },
            "median_of_run_queue_wait_quantiles_ms": {
                key: round(median(
                    r["fifo_wait_latency_ms"][key] for r in runs_for_mode
                ), 3)
                for key in METRICS
            },
            "median_actions_over_1000ms": median(
                r["actions_over_1000ms"] for r in runs_for_mode
            ),
            "median_wall_seconds": round(median(
                r["wall_seconds"] for r in runs_for_mode
            ), 3),
        }

    return {
        "kind": "LOCAL_NATIVE_VS_FIFO_WRITER_ADMISSION_SENSITIVITY_ONLY",
        "result": "SYNTHETIC_TESTS_PASSED",
        "requested_participants": participants,
        "workers": workers,
        "planner_simulations": simulations,
        "repetitions": repetitions,
        "execution_order_alternates": True,
        "all_databases_new_temporary_and_deleted": True,
        "writer_queue_process_local_only": True,
        "native_mode_is_default": True,
        "human_enrollment_authorized": False,
        "production_performance_approved": False,
        "independent_load_test_performed": False,
        "approved_slo": False,
        "performance_comparison_is_observational": True,
        "runs": runs,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=3)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--simulations", type=int, default=41)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    try:
        report = compare_writer_admission(
            participants=args.participants,
            workers=args.workers,
            simulations=args.simulations,
            repetitions=args.repetitions,
        )
    except ValueError as error:
        parser.exit(2, "INVALID SYNTHETIC BENCHMARK: " + str(error) + "\n")
    print(json.dumps(report, sort_keys=True, indent=2))
    raise SystemExit(0 if report["result"] == "SYNTHETIC_TESTS_PASSED" else 2)


if __name__ == "__main__":
    main()
