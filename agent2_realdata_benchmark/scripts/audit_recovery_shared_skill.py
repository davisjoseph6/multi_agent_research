#!/usr/bin/env python3
"""Training-only shared-skill follow-up feasibility audit.

Aggregate observational statistics; no causal or test evaluation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/assist2009"
SOURCE = ROOT / "data/processed/assist2009/interactions.parquet"

PREVIOUS = ROOT / "docs/data/recovery_followup_train_v1.json"
OUTPUT = ROOT / "docs/data/recovery_shared_skill_train_v1.json"

COLUMNS = [
    "source_row",
    "student_id",
    "event_order",
    "is_main_problem",
    "concept_ids",
    "correct",
    "first_action",
    "assistment_id",
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def clean(series):
    return series.astype("string").str.strip().replace("", pd.NA)


def skills(value):
    """Convert a list-valued concept annotation to an immutable set."""
    if value is None:
        return frozenset()

    if not isinstance(value, (list, tuple, np.ndarray)):
        raise TypeError("Unexpected concept_ids representation")

    return frozenset(
        str(item).strip()
        for item in value
        if item is not None
        and not pd.isna(item)
        and str(item).strip()
    )


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)

    gate = ROOT / "docs/phase6_test_gate_v1.md"

    require(
        "GATE CLOSED" in gate.read_text(encoding="utf-8"),
        "Held-out test gate changed",
    )

    manifest_path = SPLITS / "manifest.json"
    students_path = SPLITS / "train_students.json"

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    students = [
        str(item)
        for item in json.loads(
            students_path.read_text(encoding="utf-8")
        )
    ]

    previous = json.loads(
        PREVIOUS.read_text(encoding="utf-8")
    )

    require(
        len(students) == len(set(students)) == 2951,
        "Training-student registry changed",
    )

    require(
        sha256(SOURCE) == manifest["processed_sha256"],
        "Processed dataset changed",
    )

    require(
        previous["source_sha256"] == sha256(SOURCE)
        and previous["transition_counts"]["different_assistment"]
        == 179032
        and previous["test_outcomes_evaluated"] is False,
        "Previous follow-up audit differs",
    )

    # Project only required fields; return training students only.
    table = ds.dataset(
        str(SOURCE),
        format="parquet",
    ).to_table(
        columns=COLUMNS,
        filter=ds.field("student_id").isin(students),
    )

    train = table.to_pandas()

    require(
        len(train) == 230387,
        "Unexpected training interaction count",
    )

    train["student_id"] = train["student_id"].astype(str)

    require(
        set(train["student_id"]) == set(students),
        "Nontraining student returned",
    )

    require(
        train["source_row"].is_unique,
        "Duplicate interaction",
    )

    require(
        train["correct"].isin([0, 1]).all(),
        "Invalid binary outcomes",
    )

    require(
        not train.duplicated(
            ["student_id", "event_order"]
        ).any(),
        "Duplicate student event order",
    )

    main = train.loc[
        train["is_main_problem"].eq(True)
    ].sort_values(
        ["student_id", "event_order", "source_row"],
        kind="mergesort",
    ).reset_index(drop=True)

    require(
        len(main) == 183195,
        "Main-problem population changed",
    )

    main["skills"] = main["concept_ids"].map(skills)

    groups = main.groupby("student_id", sort=False)

    next_correct = groups["correct"].shift(-1)
    next_action = clean(
        groups["first_action"].shift(-1)
    ).fillna("missing")

    current_id = clean(main["assistment_id"])
    next_id = clean(
        groups["assistment_id"].shift(-1)
    )

    next_exists = next_correct.notna()

    different = (
        next_exists
        & current_id.notna()
        & next_id.notna()
        & current_id.ne(next_id).fillna(False)
    )

    require(
        int(next_exists.sum()) == 180244
        and int(different.sum()) == 179032,
        "Previous transition counts not reproduced",
    )

    next_skills = groups["skills"].shift(-1)

    both_tagged = (
        main["skills"].map(bool)
        & next_skills.map(
            lambda item: (
                isinstance(item, frozenset) and bool(item)
            )
        )
    )

    overlap = pd.Series(
        [
            bool(left & right)
            if isinstance(right, frozenset)
            else False
            for left, right in zip(
                main["skills"],
                next_skills,
            )
        ],
        index=main.index,
        dtype=bool,
    )

    shared = different & both_tagged & overlap
    distinct_skills = different & both_tagged & ~overlap
    missing_skills = different & ~both_tagged

    require(
        int(
            shared.sum()
            + distinct_skills.sum()
            + missing_skills.sum()
        ) == 179032,
        "Shared-skill coverage accounting failed",
    )

    next_attempt = next_action.eq("0")
    current_action = clean(
        main["first_action"]
    ).fillna("missing")

    require(
        set(current_action.unique()).issubset(
            {"0", "1", "2", "missing"}
        ),
        "Unexpected current first-action code",
    )

    require(
        set(next_action.loc[different].unique()).issubset(
            {"0", "1", "2", "missing"}
        ),
        "Unexpected next first-action code",
    )

    by_action = {}

    for code in sorted(current_action.unique()):
        anchor = current_action.eq(code)
        eligible = anchor & shared
        attempted = eligible & next_attempt

        count = int(attempted.sum())

        positive = int(
            next_correct.loc[attempted].eq(1).sum()
        )

        by_action[str(code)] = {
            "current_main_problems": int(anchor.sum()),
            "cross_assistment_followups":
                int((anchor & different).sum()),
            "shared_skill_followups":
                int(eligible.sum()),
            "shared_skill_next_answer_attempts": count,
            "shared_skill_next_hint_requests":
                int((eligible & next_action.eq("1")).sum()),
            "shared_skill_next_scaffold_requests":
                int((eligible & next_action.eq("2")).sum()),
            "shared_skill_next_missing_actions":
                int((eligible & next_action.eq("missing")).sum()),
            "positive_responses_among_next_attempts":
                positive,
            "positive_rate_among_next_attempts":
                positive / count if count else None,
        }

    require(
        sum(
            item["current_main_problems"]
            for item in by_action.values()
        ) == 183195,
        "Current-action population mismatch",
    )

    require(
        sum(
            item["shared_skill_followups"]
            for item in by_action.values()
        ) == int(shared.sum()),
        "Shared-skill group mismatch",
    )

    report = {
        "version": "recovery_shared_skill_train_v1",
        "status": "training_only_descriptive_outcome_eligibility",
        "source_sha256": sha256(SOURCE),
        "manifest_sha256": sha256(manifest_path),
        "train_students_sha256": sha256(students_path),
        "previous_audit_sha256": sha256(PREVIOUS),
        "audit_code_sha256": sha256(Path(__file__)),
        "training_students": 2951,
        "training_interactions": 230387,
        "main_problems": 183195,
        "transition_counts": {
            "different_assistment": 179032,
            "both_skill_annotated_with_overlap":
                int(shared.sum()),
            "both_skill_annotated_without_overlap":
                int(distinct_skills.sum()),
            "at_least_one_missing_skill_annotation":
                int(missing_skills.sum()),
        },
        "by_current_first_action": by_action,
        "outcome_definition": (
            "First action and correctness on the immediately "
            "next main problem, restricted to a known different "
            "ASSISTment and at least one shared annotated skill."
        ),
        "limitations": [
            "A shared skill does not establish equal difficulty.",
            "Conditioning on a next answer attempt selects a "
            "nonrandom subset of subsequent interactions.",
            "Help-seeking is voluntary, not randomized treatment.",
            "The next problem is an observed follow-up, not "
            "a verified recovery or counterfactual outcome.",
            "Within-problem action timing is unavailable.",
            "Only registered training-student rows were returned.",
        ],
        "validation_rows_returned": 0,
        "test_rows_returned": 0,
        "test_outcomes_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("SHARED-SKILL FOLLOW-UP AUDIT VERIFIED")
    print(json.dumps(report["transition_counts"], indent=2))
    print("Groups:")
    print(json.dumps(by_action, indent=2))
    print("Validation rows returned: 0")
    print("Test rows returned: 0")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
