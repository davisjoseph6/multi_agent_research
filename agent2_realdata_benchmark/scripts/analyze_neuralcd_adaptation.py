#!/usr/bin/env python3
"""Paired validation analysis: online NeuralCD versus frozen prior.

Conditional development analysis. Does not inspect test data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "results/neuralcd/validation_v1"
ONLINE = VAL / "epoch_02"
FROZEN = VAL / "epoch_02_no_adaptation"
SPLITS = ROOT / "data/splits/assist2009"
SELECTION = ROOT / "docs/data/neuralcd_checkpoint_selection_v1.json"
OUTPUT = ONLINE / "adaptation_ablation_analysis.json"

SEED = 20260921
REPLICATES = 1000
AUC_REPLICATES = 300


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ci(point, samples):
    values = np.asarray(samples, dtype=np.float64)
    if not len(values) or not np.isfinite(values).all():
        raise RuntimeError("Invalid bootstrap samples")

    lo, hi = np.quantile(values, [0.025, 0.975])

    return {
        "estimate": float(point),
        "ci95": [float(lo), float(hi)],
        "replicates": int(len(values)),
    }


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Analysis already exists: {OUTPUT}"
        )

    selection = read_json(SELECTION)
    on_report = read_json(ONLINE / "report.json")
    off_report = read_json(FROZEN / "report.json")

    assert selection["selected"]["epoch"] == 2
    assert on_report["epoch"] == off_report["epoch"] == 2
    assert on_report["status"] == "full_validation_candidate"
    assert off_report["status"] == (
        "full_validation_candidate_no_adaptation"
    )
    assert off_report["adaptation_mode"] == "frozen_prior"
    assert on_report["adaptation_learning_rate"] == 0.1
    assert on_report["adaptation_prior_penalty"] == 0.01

    assert (
        on_report["checkpoint_sha256"]
        == off_report["checkpoint_sha256"]
        == selection["selected"]["checkpoint_sha256"]
    )

    for report in (on_report, off_report):
        assert report["validation_students_processed"] == 633
        assert report["primary_targets"] == 42748
        assert report["matched_targets"] == 42437
        assert report["unsupported_targets"] == 311
        assert report["global_weights_unchanged"] is True
        assert report["test_evaluated"] is False

    on_file = ONLINE / "predictions.parquet"
    off_file = FROZEN / "predictions.parquet"

    assert sha256(on_file) == on_report["predictions_sha256"]
    assert sha256(off_file) == off_report["predictions_sha256"]

    on = pd.read_parquet(on_file).sort_values(
        "source_row"
    ).reset_index(drop=True)

    off = pd.read_parquet(off_file).sort_values(
        "source_row"
    ).reset_index(drop=True)

    assert len(on) == len(off) == 42437
    assert on["source_row"].is_unique
    assert off["source_row"].is_unique

    for column in (
        "source_row",
        "student_id",
        "event_order",
        "item_idx",
        "observed_correct",
        "prior_supported_observations",
    ):
        np.testing.assert_array_equal(
            on[column].to_numpy(),
            off[column].to_numpy(),
        )

    y = on["observed_correct"].to_numpy(dtype=np.int8)
    pn = on["predicted_probability"].to_numpy(
        dtype=np.float64
    )
    pf = off["predicted_probability"].to_numpy(
        dtype=np.float64
    )

    assert np.isin(y, [0, 1]).all()

    for p in (pn, pf):
        if (
            not np.isfinite(p).all()
            or np.any(p <= 0)
            or np.any(p >= 1)
        ):
            raise RuntimeError("Invalid prediction probabilities")

    prior = on["prior_supported_observations"].to_numpy(
        dtype=np.int64
    )

    if np.any(prior < 0):
        raise RuntimeError("Negative history length")

    zero = prior == 0

    if not zero.any():
        raise RuntimeError("No zero-history targets")

    np.testing.assert_allclose(
        pn[zero],
        pf[zero],
        atol=1e-6,
        rtol=1e-6,
    )

    def losses(p):
        return -(
            y * np.log(p)
            + (1 - y) * np.log1p(-p)
        )

    on_nll = losses(pn)
    off_nll = losses(pf)
    on_brier = (pn - y) ** 2
    off_brier = (pf - y) ** 2

    on_correct = ((pn >= 0.5) == y).astype(float)
    off_correct = ((pf >= 0.5) == y).astype(float)

    for name, report, nll, brier, correct, p in (
        ("online", on_report, on_nll, on_brier,
         on_correct, pn),
        ("frozen", off_report, off_nll, off_brier,
         off_correct, pf),
    ):
        expected = report["neuralcd"]

        computed = {
            "nll": nll.mean(),
            "brier": brier.mean(),
            "accuracy_at_0_5": correct.mean(),
            "roc_auc": roc_auc_score(y, p),
        }

        for metric, value in computed.items():
            if not np.isclose(
                value,
                expected[metric],
                atol=1e-10,
                rtol=0,
            ):
                raise RuntimeError(
                    f"{name}: {metric} does not match its report"
                )

    students = [
        str(s)
        for s in read_json(
            SPLITS / "val_students.json"
        )
    ]

    assert len(students) == 633
    assert len(set(students)) == 633

    cluster = pd.Index(students).get_indexer(
        on["student_id"].astype(str)
    )

    if np.any(cluster < 0):
        raise RuntimeError("Non-validation student found")

    counts = np.bincount(cluster, minlength=633)

    gains = {
        "nll_reduction": off_nll - on_nll,
        "brier_reduction": off_brier - on_brier,
        "accuracy_gain": on_correct - off_correct,
    }

    sums = {
        key: np.bincount(
            cluster,
            weights=values,
            minlength=633,
        )
        for key, values in gains.items()
    }

    rng = np.random.default_rng(SEED)
    samples = {key: [] for key in gains}
    auc_samples = []

    for iteration in range(REPLICATES):
        sampled = rng.integers(0, 633, size=633)
        multiplicity = np.bincount(
            sampled, minlength=633
        )

        denominator = int(
            np.dot(multiplicity, counts)
        )

        if denominator <= 0:
            raise RuntimeError("Empty bootstrap replicate")

        for key, values in sums.items():
            samples[key].append(
                float(
                    np.dot(multiplicity, values)
                    / denominator
                )
            )

        if iteration < AUC_REPLICATES:
            weights = multiplicity[cluster]

            if np.unique(y[weights > 0]).size != 2:
                raise RuntimeError(
                    "AUC bootstrap replicate has one class"
                )

            auc_samples.append(float(
                roc_auc_score(
                    y, pn, sample_weight=weights
                )
                - roc_auc_score(
                    y, pf, sample_weight=weights
                )
            ))

    results = {
        key: ci(values.mean(), samples[key])
        for key, values in gains.items()
    }

    results["auc_gain"] = ci(
        roc_auc_score(y, pn) - roc_auc_score(y, pf),
        auc_samples,
    )

    history_groups = {
        "0": prior == 0,
        "1_to_4": (prior >= 1) & (prior <= 4),
        "5_to_19": (prior >= 5) & (prior <= 19),
        "20_plus": prior >= 20,
    }

    history_results = {}

    for name, mask in history_groups.items():
        if not mask.any():
            history_results[name] = {
                "count": 0
            }
            continue

        history_results[name] = {
            "count": int(mask.sum()),
            "students": int(
                on.loc[mask, "student_id"].nunique()
            ),
            "positive_fraction": float(y[mask].mean()),
            "online_nll": float(on_nll[mask].mean()),
            "frozen_nll": float(off_nll[mask].mean()),
            "nll_reduction": float(
                gains["nll_reduction"][mask].mean()
            ),
            "brier_reduction": float(
                gains["brier_reduction"][mask].mean()
            ),
        }

    assert sum(
        row["count"]
        for row in history_results.values()
    ) == len(on)

    report = {
        "status": "conditional_validation_ablation",
        "checkpoint_epoch": 2,
        "checkpoint_sha256": on_report["checkpoint_sha256"],
        "split_assignment_sha256":
            on_report["split_assignment_sha256"],
        "online_predictions_sha256": sha256(on_file),
        "frozen_predictions_sha256": sha256(off_file),
        "students_in_split": 633,
        "students_with_matched_targets": int(
            np.count_nonzero(counts)
        ),
        "matched_targets": len(on),
        "zero_history_targets": int(zero.sum()),
        "zero_history_predictions_agree": True,
        "bootstrap_seed": SEED,
        "bootstrap_method": "paired_student_cluster",
        "bootstrap_results": results,
        "history_groups": history_results,
        "limitation": (
            "Development analysis conditional on selecting epoch 2 "
            "using online-adaptation validation NLL. Bootstrap "
            "intervals do not correct for model-selection bias. "
            "History groups are exploratory."
        ),
        "test_evaluated": False,
    }

    OUTPUT.write_text(
        json.dumps(
            report, indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
