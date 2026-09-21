#!/usr/bin/env python3
"""Descriptive validation calibration: selected NeuralCD versus BKT.

No calibrator is fitted. No test data are accessed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

NEURAL_DIR = (
    ROOT / "results/neuralcd/validation_grid_v1"
    / "lr0p1_pen0p1/epoch_02"
)

BKT_FILE = (
    ROOT / "results/bkt/frozen_v1_validation_predictions.parquet"
)

OUTPUT = DOCS / "neuralcd_calibration_diagnostics_v1.json"

N_BINS = 10


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def check_probabilities(y, p):
    if len(y) != len(p) or len(y) == 0:
        raise RuntimeError("Invalid prediction population")

    if not np.isin(y, [0, 1]).all():
        raise RuntimeError("Nonbinary outcomes")

    if (
        not np.isfinite(p).all()
        or np.any(p <= 0)
        or np.any(p >= 1)
    ):
        raise RuntimeError("Invalid probability")


def reliability(y, p):
    """Equal-width ECE on [0,1], with ten fixed bins."""
    check_probabilities(y, p)

    indices = np.minimum(
        (p * N_BINS).astype(np.int64),
        N_BINS - 1,
    )

    rows = []
    ece = 0.0
    maximum_gap = 0.0

    for index in range(N_BINS):
        mask = indices == index
        count = int(mask.sum())

        if count == 0:
            rows.append({
                "bin": index,
                "lower_inclusive": index / N_BINS,
                "upper_exclusive_except_last":
                    (index + 1) / N_BINS,
                "count": 0,
                "mean_probability": None,
                "observed_positive_fraction": None,
                "signed_gap_predicted_minus_observed": None,
                "absolute_gap": None,
            })
            continue

        mean_prediction = float(p[mask].mean())
        observed = float(y[mask].mean())
        signed_gap = mean_prediction - observed
        gap = abs(signed_gap)

        ece += (count / len(y)) * gap
        maximum_gap = max(maximum_gap, gap)

        rows.append({
            "bin": index,
            "lower_inclusive": index / N_BINS,
            "upper_exclusive_except_last":
                (index + 1) / N_BINS,
            "count": count,
            "mean_probability": mean_prediction,
            "observed_positive_fraction": observed,
            "signed_gap_predicted_minus_observed":
                signed_gap,
            "absolute_gap": gap,
        })

    if sum(row["count"] for row in rows) != len(y):
        raise RuntimeError("Calibration-bin accounting failed")

    return {
        "ece_10_equal_width": float(ece),
        "maximum_nonempty_bin_gap": float(maximum_gap),
        "nonempty_bins": sum(
            row["count"] > 0 for row in rows
        ),
        "bins": rows,
    }


def summarize(y, p):
    check_probabilities(y, p)

    losses = -(
        y * np.log(p)
        + (1 - y) * np.log1p(-p)
    )

    calibration = reliability(y, p)

    return {
        "count": int(len(y)),
        "positive_fraction": float(y.mean()),
        "mean_probability": float(p.mean()),
        "mean_probability_minus_positive_fraction":
            float(p.mean() - y.mean()),
        "nll": float(losses.mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy_at_0_5": float(
            np.mean((p >= 0.5) == y)
        ),
        "roc_auc": (
            float(roc_auc_score(y, p))
            if np.unique(y).size == 2
            else None
        ),
        "fraction_below_0_01": float(
            np.mean(p < 0.01)
        ),
        "fraction_above_0_99": float(
            np.mean(p > 0.99)
        ),
        "probability_quantiles": {
            str(q): float(np.quantile(p, q))
            for q in (0.01, 0.05, 0.5, 0.95, 0.99)
        },
        "calibration": calibration,
    }


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite calibration report: {OUTPUT}"
        )

    selection = read_json(
        DOCS / "neuralcd_grid_selection_v1.json"
    )
    readiness = read_json(
        DOCS / "neuralcd_readiness_v1.json"
    )
    history = read_json(
        DOCS / "neuralcd_history_access_v1.json"
    )
    manifest = read_json(
        ROOT / "data/splits/assist2009/manifest.json"
    )

    chosen = selection["selected"]

    assert selection["candidates_verified"] == 45
    assert selection["test_evaluated"] is False

    assert chosen["epoch"] == 2
    assert chosen["learning_rate"] == 0.1
    assert chosen["prior_penalty"] == 0.1

    assert (
        history["selected_predictions_sha256"]
        == chosen["predictions_sha256"]
    )

    assert (
        selection["matched_targets"]
        == history["groups"]["all_matched"]["count"]
        == 42437
    )

    neural_file = NEURAL_DIR / "predictions.parquet"
    neural_report_file = NEURAL_DIR / "report.json"

    assert sha256(neural_file) == (
        chosen["predictions_sha256"]
    )

    assert sha256(neural_report_file) == (
        chosen["report_sha256"]
    )

    assert sha256(BKT_FILE) == (
        readiness["frozen_prediction_sha256"]
    )

    neural_report = read_json(neural_report_file)

    assert neural_report["test_evaluated"] is False
    assert neural_report["global_weights_unchanged"] is True
    assert neural_report["matched_targets"] == 42437

    assert (
        neural_report["split_assignment_sha256"]
        == manifest["assignment_sha256"]
    )

    neural = pd.read_parquet(
        neural_file,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
            "predicted_probability",
            "prior_supported_observations",
        ],
    ).rename(columns={
        "observed_correct": "neural_label",
        "predicted_probability": "neural_probability",
    })

    bkt = pd.read_parquet(
        BKT_FILE,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
            "predicted_probability",
        ],
    ).rename(columns={
        "observed_correct": "bkt_label",
        "predicted_probability": "bkt_probability",
    })

    neural["student_id"] = neural["student_id"].astype(str)
    bkt["student_id"] = bkt["student_id"].astype(str)

    if (
        not neural["source_row"].is_unique
        or not bkt["source_row"].is_unique
    ):
        raise RuntimeError("Duplicate prediction source rows")

    joined = neural.merge(
        bkt,
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
    ).sort_values("source_row").reset_index(drop=True)

    if len(joined) != len(neural) or len(neural) != 42437:
        raise RuntimeError("Matched population mismatch")

    if len(joined) != 42437:
        raise RuntimeError("Missing matched predictions")

    np.testing.assert_array_equal(
        joined["neural_label"].to_numpy(),
        joined["bkt_label"].to_numpy(),
    )

    y = joined["neural_label"].to_numpy(
        dtype=np.int64
    )

    pn = joined["neural_probability"].to_numpy(
        dtype=np.float64
    )

    pb = joined["bkt_probability"].to_numpy(
        dtype=np.float64
    )

    prior = joined[
        "prior_supported_observations"
    ].to_numpy(dtype=np.int64)

    if np.any(prior < 0):
        raise RuntimeError("Negative history length")

    full_neural = summarize(y, pn)
    full_bkt = summarize(y, pb)

    for name, result, reference in (
        (
            "NeuralCD",
            full_neural,
            neural_report["neuralcd"],
        ),
        (
            "BKT",
            full_bkt,
            neural_report["matched_bkt"],
        ),
    ):
        for metric in (
            "nll",
            "brier",
            "accuracy_at_0_5",
            "roc_auc",
        ):
            np.testing.assert_allclose(
                result[metric],
                reference[metric],
                atol=1e-10,
                rtol=0,
                err_msg=f"{name} {metric} differs",
            )

    groups = {
        "0": prior == 0,
        "1_to_4": (prior >= 1) & (prior <= 4),
        "5_to_19": (prior >= 5) & (prior <= 19),
        "20_plus": prior >= 20,
    }

    expected_counts = {
        "0": 626,
        "1_to_4": 2288,
        "5_to_19": 5973,
        "20_plus": 33550,
    }

    group_results = {}

    for name, mask in groups.items():
        if int(mask.sum()) != expected_counts[name]:
            raise RuntimeError(
                f"Unexpected history-group count: {name}"
            )

        group_results[name] = {
            "students": int(
                joined.loc[mask, "student_id"].nunique()
            ),
            "neuralcd": summarize(y[mask], pn[mask]),
            "bkt": summarize(y[mask], pb[mask]),
        }

    if sum(expected_counts.values()) != 42437:
        raise RuntimeError("History groups do not partition targets")

    if group_results["0"]["neuralcd"]["count"] != 626:
        raise RuntimeError("Zero-history count mismatch")

    results = {
        "status": "descriptive_validation_calibration",
        "selected_epoch": 2,
        "learning_rate": 0.1,
        "prior_penalty": 0.1,
        "split_assignment_sha256":
            manifest["assignment_sha256"],
        "neural_predictions_sha256": sha256(neural_file),
        "bkt_predictions_sha256": sha256(BKT_FILE),
        "matched_targets": 42437,
        "students_with_targets": int(
            joined["student_id"].nunique()
        ),
        "binning": (
            "Ten equal-width bins on [0,1]; left-inclusive, "
            "right-exclusive except the final bin."
        ),
        "full_population": {
            "neuralcd": full_neural,
            "bkt": full_bkt,
        },
        "by_neuralcd_supported_history": group_results,
        "interpretation_limitations": (
            "ECE depends on bin choice and is descriptive. "
            "Student responses are clustered. The configuration "
            "was selected using validation outcomes. No "
            "calibration transformation was fitted. Binary "
            "response labels are not direct measures of mastery."
        ),
        "calibrator_fitted": False,
        "test_evaluated": False,
    }

    OUTPUT.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== FULL VALIDATION CALIBRATION ===")

    for name, result in (
        ("NeuralCD", full_neural),
        ("BKT", full_bkt),
    ):
        print(f"\n{name}")
        print("NLL:", result["nll"])
        print("Brier:", result["brier"])
        print("ECE10:", result["calibration"]["ece_10_equal_width"])
        print("Mean prediction:", result["mean_probability"])
        print("Observed positive rate:", result["positive_fraction"])
        print("Nonempty bins:", result["calibration"]["nonempty_bins"])

    print("\n=== HISTORY-GROUP CALIBRATION ===")

    for name, group in group_results.items():
        n = group["neuralcd"]["count"]

        print(
            name,
            "n=", n,
            "NeuralCD ECE=",
            group["neuralcd"]["calibration"]["ece_10_equal_width"],
            "BKT ECE=",
            group["bkt"]["calibration"]["ece_10_equal_width"],
        )

    print("\nCALIBRATION ANALYSIS VERIFIED")
    print("Calibrator fitted: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
