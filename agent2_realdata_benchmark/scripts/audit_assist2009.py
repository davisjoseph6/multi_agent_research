#!/usr/bin/env python3
"""Audit ASSISTments before preprocessing or model training."""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/assist2009/skill_builder_data_corrected_collapsed.csv"
OUTPUT = ROOT / "results/data_audit_assist2009.json"

COLUMNS = [
    "order_id",
    "user_id",
    "problem_id",
    "skill_id",
    "skill_name",
    "correct",
    "original",
    "ms_first_response",
    "attempt_count",
    "first_action",
]


def counts(series: pd.Series) -> dict:
    """Return JSON-safe categorical value counts."""
    return {
        str(key): int(value)
        for key, value in series.value_counts(
            dropna=False
        ).head(15).items()
    }


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    df = pd.read_csv(
        SOURCE,
        usecols=COLUMNS,
        dtype="string",
        encoding="latin1",
        low_memory=False,
    )

    skills = df["skill_id"].dropna()
    variants = df.groupby("problem_id")["skill_id"].nunique()

    report = {
        "source_file": SOURCE.name,
        "rows": int(len(df)),
        "students": int(df["user_id"].nunique()),
        "questions": int(df["problem_id"].nunique()),
        "unique_raw_skill_values": int(
            df["skill_id"].nunique()
        ),
        "missing_values": {
            col: int(df[col].isna().sum())
            for col in COLUMNS
        },
        "duplicate_order_ids": int(
            df.duplicated(["order_id"]).sum()
        ),
        "duplicate_student_order_pairs": int(
            df.duplicated(
                ["user_id", "order_id"]
            ).sum()
        ),
        "exact_duplicate_selected_rows": int(
            df.duplicated().sum()
        ),
        "invalid_correct_values": int(
            (~df["correct"].isin(["0", "1"])).sum()
        ),
        "correct_distribution": counts(df["correct"]),
        "original_distribution": counts(df["original"]),
        "first_action_distribution": counts(
            df["first_action"]
        ),
        "student_interaction_quantiles": {
            str(q): float(value)
            for q, value in df.groupby(
                "user_id"
            ).size().quantile(
                [0, 0.25, 0.5, 0.75, 1.0]
            ).items()
        },
        "skill_values_containing_underscore": int(
            skills.str.contains(
                "_", regex=False
            ).sum()
        ),
        "skill_values_containing_comma": int(
            skills.str.contains(
                ",", regex=False
            ).sum()
        ),
        "skill_values_containing_semicolon": int(
            skills.str.contains(
                ";", regex=False
            ).sum()
        ),
        "sample_skill_values": [
            str(x) for x in skills.drop_duplicates().head(20)
        ],
        "questions_with_multiple_skill_encodings": int(
            (variants > 1).sum()
        ),
        "missing_order_ids": int(
            df["order_id"].isna().sum()
        ),
        "non_numeric_order_ids": int(
            pd.to_numeric(
                df["order_id"], errors="coerce"
            ).isna().sum()
        ),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
