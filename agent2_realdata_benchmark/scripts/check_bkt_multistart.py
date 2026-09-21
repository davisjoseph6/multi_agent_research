#!/usr/bin/env python3
"""Check shared BKT parameter-fit robustness using training data only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from scripts.fit_bkt import (
    BOUNDS,
    load_sequences,
    run_partition,
)
from src.models.bkt import BKTParams


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/bkt"

# These starting values are fixed before running this experiment.
STARTS = {
    "low_initial_mastery": [0.15, 0.05, 0.15, 0.15],
    "high_initial_mastery": [0.85, 0.20, 0.30, 0.10],
}

LOSS_TOLERANCE = 0.002


def parameter_dict(values):
    names = [
        "initial_mastery",
        "learning",
        "slip",
        "guess",
    ]
    return {
        name: float(value)
        for name, value in zip(names, values, strict=True)
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def main():
    existing_path = RESULTS / "fit_report.json"

    if not existing_path.is_file():
        raise FileNotFoundError(existing_path)

    original = json.loads(existing_path.read_text())

    if not original["optimizer"]["success"]:
        raise RuntimeError(
            "Original BKT optimization did not converge"
        )

    sequences, num_concepts, manifest = load_sequences()

    train = sequences["train"]

    if original["split_assignment_sha256"] != (
        manifest["assignment_sha256"]
    ):
        raise RuntimeError("Original fit uses a different split")

    original_values = np.array([
        original["fitted_parameters"][name]
        for name in (
            "initial_mastery",
            "learning",
            "slip",
            "guess",
        )
    ], dtype=float)

    original_params = BKTParams(*original_values)

    verified_original_nll, _ = run_partition(
        original_params,
        train,
        num_concepts,
    )

    if not np.isclose(
        verified_original_nll,
        original["fitted_train_nll"],
        atol=1e-9,
        rtol=0,
    ):
        raise RuntimeError(
            "Original training result cannot be reproduced"
        )

    runs = [{
        "name": "original_converged_fit",
        "source": "results/bkt/fit_report.json",
        "success": True,
        "training_nll": float(verified_original_nll),
        "parameters": parameter_dict(original_values),
    }]

    for name, start in STARTS.items():
        print(
            f"\n=== Fitting from {name}: {start} ===",
            flush=True,
        )

        count = 0

        def objective(values):
            nonlocal count

            params = BKTParams(*map(float, values))

            loss, _ = run_partition(
                params,
                train,
                num_concepts,
            )

            count += 1

            if count == 1 or count % 20 == 0:
                print(
                    f"{name}: evaluation={count}, "
                    f"training_NLL={loss:.8f}",
                    flush=True,
                )

            return loss

        result = minimize(
            objective,
            np.asarray(start, dtype=float),
            method="L-BFGS-B",
            bounds=BOUNDS,
            options={
                "maxiter": 55,
                "maxfun": 180,
                "eps": 1e-4,
                "ftol": 1e-8,
            },
        )

        fitted_values = result.x.astype(float)

        final_params = BKTParams(*fitted_values)

        verified_loss, _ = run_partition(
            final_params,
            train,
            num_concepts,
        )

        near_bounds = {}

        for index, (lower, upper) in enumerate(BOUNDS):
            name_param = (
                "initial_mastery",
                "learning",
                "slip",
                "guess",
            )[index]

            value = fitted_values[index]

            near_bounds[name_param] = bool(
                min(value - lower, upper - value) < 0.005
            )

        record = {
            "name": name,
            "starting_parameters": parameter_dict(start),
            "success": bool(result.success),
            "optimizer_message": str(result.message),
            "iterations": int(result.nit),
            "function_evaluations": int(result.nfev),
            "training_nll": float(verified_loss),
            "parameters": parameter_dict(fitted_values),
            "near_parameter_bounds": near_bounds,
        }

        runs.append(record)

        # Save each completed run separately. An interrupted later
        # optimization will not erase this result.
        write_json(
            RESULTS / "multistart" / f"{name}.json",
            record,
        )

        print(
            json.dumps(record, indent=2),
            flush=True,
        )

    successful = [
        run for run in runs
        if run["success"]
    ]

    if not successful:
        raise RuntimeError("No converged fits")

    winner = min(
        successful,
        key=lambda run: run["training_nll"],
    )

    converged_losses = [
        run["training_nll"]
        for run in successful
    ]

    loss_range = (
        max(converged_losses) - min(converged_losses)
    )

    parameter_spread = {}

    for name in (
        "initial_mastery",
        "learning",
        "slip",
        "guess",
    ):
        values = [
            run["parameters"][name]
            for run in successful
        ]

        parameter_spread[name] = float(
            max(values) - min(values)
        )

    all_converged = all(run["success"] for run in runs)

    report = {
        "experiment": "BKT training-only multistart",
        "dataset": manifest["dataset"],
        "split_seed": manifest["seed"],
        "split_assignment_sha256": (
            manifest["assignment_sha256"]
        ),
        "test_partition_used": False,
        "runs": runs,
        "best_converged_fit": winner,
        "all_runs_converged": all_converged,
        "converged_training_nll_range": float(loss_range),
        "parameter_spread": parameter_spread,
        "loss_tolerance": LOSS_TOLERANCE,
        "status": (
            "training_objective_stable"
            if all_converged
            and loss_range <= LOSS_TOLERANCE
            else "review_required"
        ),
    }

    output = RESULTS / "multistart_report.json"

    write_json(output, report)

    print("\n=== FINAL SUMMARY ===")
    print(json.dumps({
        "status": report["status"],
        "best_converged_fit": winner["name"],
        "best_training_nll": winner["training_nll"],
        "training_nll_range": loss_range,
        "parameter_spread": parameter_spread,
    }, indent=2))

    print("\nSaved:", output)


if __name__ == "__main__":
    main()
