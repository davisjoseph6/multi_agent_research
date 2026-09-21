#!/usr/bin/env python3
"""Training-only, descriptive cross-ASSISTment follow-up audit."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/assist2009"
SOURCE = ROOT / "data/processed/assist2009/interactions.parquet"
OUTPUT = ROOT / "docs/data/recovery_followup_train_v1.json"

COLUMNS = [
    "source_row",
    "student_id",
    "event_order",
    "is_main_problem",
    "correct",
    "first_action",
    "assistment_id",
]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def clean(series):
    return series.astype("string").str.strip().replace("", pd.NA)


def rate(series):
    return float(series.mean()) if len(series) else None


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)

    gate = ROOT / "docs/phase6_test_gate_v1.md"
    require(
        "GATE CLOSED" in gate.read_text(),
        "Test gate is not closed",
    )

    manifest_file = SPLITS / "manifest.json"
    students_file = SPLITS / "train_students.json"

    manifest = json.loads(manifest_file.read_text())
    students = json.loads(students_file.read_text())
    students = [str(s) for s in students]

    require(
        len(students) == len(set(students)) == 2951,
        "Training registry mismatch",
    )
    require(
        digest(SOURCE) == manifest["processed_sha256"],
        "Processed data changed",
    )

    # Project and filter before materializing rows.
    table = ds.dataset(
        str(SOURCE), format="parquet"
    ).to_table(
        columns=COLUMNS,
        filter=ds.field("student_id").isin(students),
    )

    df = table.to_pandas()

    require(len(df) == 230387, "Training row count changed")
    require(
        set(df["student_id"].astype(str)) == set(students),
        "Nontraining student returned",
    )
    require(
        df["source_row"].is_unique,
        "Duplicate source rows",
    )
    require(
        df["correct"].isin([0, 1]).all(),
        "Invalid outcomes",
    )
    require(
        not df.duplicated(
            ["student_id", "event_order"]
        ).any(),
        "Duplicate student event order",
    )

    main_df = df.loc[
        df["is_main_problem"].eq(True)
    ].sort_values(
        ["student_id", "event_order", "source_row"],
        kind="mergesort",
    ).reset_index(drop=True)

    require(
        len(main_df) == 183195,
        "Main-problem population changed",
    )

    groups = main_df.groupby("student_id", sort=False)

    next_correct = groups["correct"].shift(-1)
    next_action = clean(groups["first_action"].shift(-1))

    current_id = clean(main_df["assistment_id"])
    next_id = clean(groups["assistment_id"].shift(-1))

    next_exists = next_correct.notna()
    identifiable = current_id.notna() & next_id.notna()

    same = (
        next_exists
        & identifiable
        & current_id.eq(next_id).fillna(False)
    )

    different = (
        next_exists
        & identifiable
        & current_id.ne(next_id).fillna(False)
    )

    unknown = next_exists & ~identifiable
    terminal = ~next_exists

    require(
        int(next_exists.sum()) == 180244,
        "Previous follow-up count changed",
    )
    require(
        int(same.sum()) == 1212,
        "Previous same-ASSISTment count changed",
    )
    require(
        int(
            same.sum() + different.sum() + unknown.sum()
            + terminal.sum()
        ) == len(main_df),
        "Transition categories do not partition main problems",
    )

    action = clean(main_df["first_action"]).fillna("missing")

    require(
        set(action.unique()).issubset(
            {"0", "1", "2", "missing"}
        ),
        "Unexpected action code",
    )

    by_action = {}

    for code in sorted(action.unique()):
        anchor = action.eq(code)
        eligible = anchor & different

        later_correct = next_correct.loc[eligible]
        later_action = next_action.loc[eligible]

        by_action[str(code)] = {
            "main_problems": int(anchor.sum()),
            "cross_assistment_followups": int(eligible.sum()),
            "next_positive_response_rate":
                rate(later_correct),
            "next_answer_attempt_count":
                int(later_action.eq("0").sum()),
            "next_hint_request_count":
                int(later_action.eq("1").sum()),
            "next_scaffold_request_count":
                int(later_action.eq("2").sum()),
            "next_missing_action_count":
                int(later_action.isna().sum()),
        }

    report = {
        "version": "recovery_followup_train_v1",
        "status": "training_only_descriptive_followup",
        "source_sha256": digest(SOURCE),
        "manifest_sha256": digest(manifest_file),
        "train_students_sha256": digest(students_file),
        "audit_code_sha256": digest(Path(__file__)),
        "training_students": 2951,
        "training_interactions": len(df),
        "main_problems": len(main_df),
        "transition_counts": {
            "next_main_exists": int(next_exists.sum()),
            "same_assistment": int(same.sum()),
            "different_assistment": int(different.sum()),
            "unknown_assistment_relationship":
                int(unknown.sum()),
            "no_next_main": int(terminal.sum()),
        },
        "by_current_first_action": by_action,
        "outcome_definition": (
            "Correctness of immediately next main problem, "
            "restricted to known different ASSISTment IDs."
        ),
        "interpretation": (
            "Descriptive longitudinal association only. "
            "Voluntary help-seeking is confounded. "
            "Later correct=0 can include a help request. "
            "No treatment effect is identified."
        ),
        "validation_rows_returned": 0,
        "test_rows_returned": 0,
        "test_outcomes_evaluated": False,
        "test_gate": "closed",
    }

    require(
        sum(
            row["main_problems"]
            for row in by_action.values()
        ) == len(main_df),
        "Action-group accounting mismatch",
    )

    require(
        sum(
            row["cross_assistment_followups"]
            for row in by_action.values()
        ) == int(different.sum()),
        "Follow-up accounting mismatch",
    )

    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )

    print("CROSS-ASSISTMENT FOLLOW-UP AUDIT VERIFIED")
    print(json.dumps(report["transition_counts"], indent=2))
    print("First-action groups:")
    print(json.dumps(by_action, indent=2))
    print("Validation rows returned: 0")
    print("Test rows returned: 0")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
