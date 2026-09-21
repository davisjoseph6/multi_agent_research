#!/usr/bin/env python3
"""Aggregate recovery feasibility on registered training students only.

Observational descriptions only. No test or validation records
are returned by the student-ID filter. No causal claims.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/assist2009"
SOURCE = ROOT / "data/processed/assist2009/interactions.parquet"
OUTPUT = ROOT / "docs/data/recovery_feasibility_train_v1.json"

COLUMNS = [
    "source_row",
    "student_id",
    "event_order",
    "is_main_problem",
    "is_primary_target",
    "correct",
    "first_action",
    "hint_count",
    "assistment_id",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def cleaned_ids(series: pd.Series) -> pd.Series:
    """Normalize missing or empty ASSISTment identifiers."""
    return (
        series.astype("string")
        .str.strip()
        .replace("", pd.NA)
    )


def optional_rate(series: pd.Series):
    """Return a JSON-safe observed mean, or null if unavailable."""
    if len(series) == 0:
        return None
    return float(series.astype(float).mean())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(
            f"Existing feasibility report: {OUTPUT}"
        )

    gate = ROOT / "docs/phase6_test_gate_v1.md"
    require(
        "GATE CLOSED" in gate.read_text(encoding="utf-8"),
        "Held-out test gate is not closed",
    )

    manifest_path = SPLITS / "manifest.json"
    students_path = SPLITS / "train_students.json"

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    student_list = json.loads(
        students_path.read_text(encoding="utf-8")
    )

    require(
        isinstance(student_list, list),
        "Training students must be a list",
    )

    student_ids = [str(value) for value in student_list]

    require(
        len(student_ids)
        == len(set(student_ids))
        == manifest["student_counts"]["train"]
        == 2951,
        "Training-student registry mismatch",
    )

    require(
        sha256(SOURCE) == manifest["processed_sha256"],
        "Processed dataset checksum mismatch",
    )

    # The Arrow filter is applied BEFORE converting rows to Pandas.
    # The filter's allowed IDs come exclusively from train_students.json.
    dataset = ds.dataset(str(SOURCE), format="parquet")

    table = dataset.to_table(
        columns=COLUMNS,
        filter=ds.field("student_id").isin(student_ids),
    )

    train = table.to_pandas()

    # Validate the returned population before doing any analysis.
    require(
        list(train.columns) == COLUMNS,
        "Unexpected projected data columns",
    )

    require(
        len(train) == 230387,
        "Unexpected number of training interactions",
    )

    train["student_id"] = train["student_id"].astype(str)

    require(
        set(train["student_id"]) == set(student_ids),
        "Filtered data contain incorrect student identities",
    )

    require(
        train["source_row"].is_unique,
        "Duplicate source rows",
    )

    require(
        train["correct"].notna().all()
        and train["correct"].isin([0, 1]).all(),
        "Invalid binary outcome coding",
    )

    require(
        train["event_order"].notna().all(),
        "Missing event order",
    )

    require(
        train["is_main_problem"].notna().all()
        and train["is_primary_target"].notna().all(),
        "Missing problem classification",
    )

    duplicate_orders = int(
        train.duplicated(
            ["student_id", "event_order"]
        ).sum()
    )

    train = train.sort_values(
        ["student_id", "event_order", "source_row"],
        kind="mergesort",
    ).reset_index(drop=True)

    train["action"] = (
        train["first_action"]
        .astype("string")
        .fillna("missing")
        .str.strip()
        .replace("", "missing")
    )

    action_codes = set(train["action"].unique())

    require(
        action_codes.issubset({"0", "1", "2", "missing"}),
        f"Unexpected first-action codes: {action_codes}",
    )

    hints = (
        train["hint_count"]
        .astype("string")
        .str.strip()
    )

    hint_present = (
        hints.notna() & hints.ne("").fillna(False)
    )

    hint_numeric = pd.to_numeric(
        hints.where(hint_present),
        errors="coerce",
    )

    malformed_hints = int(
        (hint_present & hint_numeric.isna()).sum()
    )

    main_mask = train["is_main_problem"].eq(True)

    main = train.loc[main_mask].copy()

    require(
        main["is_primary_target"].isin([True, False]).all(),
        "Invalid primary-target flags",
    )

    # The next main problem is computed WITHIN each student,
    # never across student boundaries.
    main_groups = main.groupby(
        "student_id",
        sort=False,
    )

    main["next_main_correct"] = main_groups[
        "correct"
    ].shift(-1)

    main["next_main_event_order"] = main_groups[
        "event_order"
    ].shift(-1)

    main["next_main_assistment_id"] = main_groups[
        "assistment_id"
    ].shift(-1)

    next_available = main["next_main_correct"].notna()

    current_assistment = cleaned_ids(
        main["assistment_id"]
    )

    next_assistment = cleaned_ids(
        main["next_main_assistment_id"]
    )

    same_assistment = (
        next_available
        & current_assistment.notna()
        & next_assistment.notna()
        & current_assistment.eq(
            next_assistment
        ).fillna(False)
    )

    # Check whether the very next recorded interaction
    # is scaffolding under the same ASSISTment identifier.
    all_groups = train.groupby(
        "student_id",
        sort=False,
    )

    next_event_is_main = all_groups[
        "is_main_problem"
    ].shift(-1)

    next_event_assistment = cleaned_ids(
        all_groups["assistment_id"].shift(-1)
    )

    event_assistment = cleaned_ids(
        train["assistment_id"]
    )

    immediate_scaffold = (
        main_mask
        & next_event_is_main.eq(False).fillna(False)
        & event_assistment.notna()
        & next_event_assistment.notna()
        & event_assistment.eq(
            next_event_assistment
        ).fillna(False)
    )

    by_action = {}

    for action, group in main.groupby(
        "action",
        sort=True,
    ):
        available = group[
            "next_main_correct"
        ].notna()

        future = group.loc[
            available, "next_main_correct"
        ]

        by_action[str(action)] = {
            "main_problems": int(len(group)),
            "current_positive_response_rate":
                optional_rate(group["correct"]),
            "with_next_main_problem":
                int(available.sum()),
            "without_next_main_problem":
                int((~available).sum()),
            "next_main_positive_response_rate":
                optional_rate(future),
            "next_main_same_assistment":
                int(same_assistment.loc[
                    group.index
                ].sum()),
        }

    # All reported quantities are aggregates.
    report = {
        "version": "recovery_feasibility_train_v1",
        "status": "training_only_observational_audit",
        "data_provenance": {
            "processed_sha256": sha256(SOURCE),
            "manifest_sha256": sha256(manifest_path),
            "train_students_sha256": sha256(students_path),
            "audit_code_sha256": sha256(Path(__file__)),
            "student_filter": "registered_train_students_only",
            "columns_projected": COLUMNS,
        },
        "population": {
            "training_students": int(
                train["student_id"].nunique()
            ),
            "training_interactions": int(len(train)),
            "main_problems": int(main_mask.sum()),
            "scaffolding_interactions":
                int((~main_mask).sum()),
            "primary_targets": int(
                train["is_primary_target"].sum()
            ),
            "duplicate_student_event_orders":
                duplicate_orders,
        },
        "first_action_all_interactions": {
            str(key): int(value)
            for key, value in train[
                "action"
            ].value_counts(
                dropna=False
            ).items()
        },
        "hint_count_quality": {
            "nonempty": int(hint_present.sum()),
            "parseable_numeric": int(
                hint_numeric.notna().sum()
            ),
            "nonempty_unparseable": malformed_hints,
            "negative_numeric_values": int(
                (hint_numeric < 0).sum()
            ),
        },
        "sequence_availability": {
            "main_with_next_main":
                int(next_available.sum()),
            "main_without_next_main":
                int((~next_available).sum()),
            "next_main_same_assistment":
                int(same_assistment.sum()),
            "immediate_next_record_scaffold_same_assistment":
                int(immediate_scaffold.sum()),
        },
        "main_problem_groups_by_first_action":
            by_action,
        "limitations": [
            "First action is observed during an interaction, "
            "not an available pre-response predictor.",
            "Next main problem is the next recorded main row "
            "within the same student, not a causal outcome.",
            "Voluntary help requests are not randomized treatment.",
            "Correct=0 includes help-request outcome coding.",
            "Event order does not recover exact within-problem "
            "hint and attempt timing.",
            "The analysis does not administer an intervention.",
            "Arrow filtering guarantees returned training rows; "
            "physical mixed-row-group reads are not ruled out.",
        ],
        "validation_rows_returned": 0,
        "test_rows_returned": 0,
        "test_outcomes_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("TRAINING-ONLY RECOVERY FEASIBILITY AUDIT VERIFIED")
    print(
        "Training students:",
        report["population"]["training_students"],
    )
    print(
        "Training interactions:",
        report["population"]["training_interactions"],
    )
    print(
        "Main problems:",
        report["population"]["main_problems"],
    )
    print(
        "Main problems with next main:",
        report["sequence_availability"]["main_with_next_main"],
    )
    print("Validation rows returned: 0")
    print("Test rows returned: 0")
    print("Test outcomes evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
