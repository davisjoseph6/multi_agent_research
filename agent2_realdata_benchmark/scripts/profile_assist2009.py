#!/usr/bin/env python3
"""Profile corrected ASSISTments before defining preprocessing rules."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "data/raw/assist2009/"
    "skill_builder_data_corrected_collapsed.csv"
)


def main() -> None:
    """Inspect concept coverage, scaffolding, repeats and label semantics."""
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    header = pd.read_csv(
        SOURCE, nrows=0, encoding="latin1"
    ).columns.tolist()

    required = [
        "order_id", "user_id", "problem_id", "skill_id",
        "skill_name", "correct", "original", "first_action",
    ]
    optional = ["answer_type", "assistment_id", "hint_count"]

    missing = set(required) - set(header)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    columns = required + [c for c in optional if c in header]
    df = pd.read_csv(
        SOURCE,
        usecols=columns,
        dtype="string",
        encoding="latin1",
        low_memory=False,
    )

    missing_skill = (
        df["skill_id"].isna()
        | df["skill_id"].str.strip().fillna("").eq("")
    )

    print("\n=== OVERALL ===")
    print("Rows:", len(df))
    print("Missing skill IDs:", int(missing_skill.sum()))
    print("Available skill IDs:", int((~missing_skill).sum()))

    print("\n=== MAIN VS SCAFFOLD ===")
    print(df["original"].value_counts(dropna=False).to_string())

    print("\n=== MISSING SKILL BY PROBLEM TYPE ===")
    print(pd.crosstab(
        df["original"].fillna("<MISSING>"),
        missing_skill,
        rownames=["original"],
        colnames=["skill_missing"],
    ).to_string())

    print("\n=== FIRST ACTION BY PROBLEM TYPE ===")
    print(pd.crosstab(
        df["original"].fillna("<MISSING>"),
        df["first_action"].fillna("<MISSING>"),
    ).to_string())

    print("\n=== FIRST ACTION VS CORRECTNESS ===")
    print(pd.crosstab(
        df["first_action"].fillna("<MISSING>"),
        df["correct"].fillna("<MISSING>"),
    ).to_string())

    print("\n=== REPEATED STUDENT-QUESTION PAIRS ===")
    print("Repeated rows:", int(
        df.duplicated(["user_id", "problem_id"]).sum()
    ))

    print("\n=== QUESTION SKILL ANNOTATION COVERAGE ===")
    item_info = pd.DataFrame({
        "problem_id": df["problem_id"],
        "tagged": ~missing_skill,
    })

    item_coverage = item_info.groupby("problem_id")["tagged"].agg(
        ["sum", "count"]
    )

    tagged = item_coverage["sum"]
    untagged = item_coverage["count"] - tagged

    print("Questions always tagged:", int((untagged == 0).sum()))
    print("Questions always untagged:", int((tagged == 0).sum()))
    print("Questions with mixed coverage:", int(
        ((tagged > 0) & (untagged > 0)).sum()
    ))

    print("\n=== CONCEPT ID PARSING ===")
    skill_strings = df.loc[~missing_skill, "skill_id"]
    tokens = skill_strings.str.split("_").explode()
    invalid = ~tokens.str.fullmatch(r"[0-9]+")

    print("Unique individual skill IDs:", tokens.nunique())
    print("Invalid individual skill tokens:", int(invalid.sum()))
    print("Largest skills-per-interaction:", int(
        skill_strings.str.count("_").max() + 1
    ))

    print("\n=== LABEL SEMANTICS ===")
    for column in ["answer_type", "hint_count"]:
        if column in df.columns:
            print(f"\n{column}:")
            print(df[column].value_counts(
                dropna=False
            ).head(15).to_string())

    if "answer_type" in df.columns:
        print("\nAnswer type vs correctness:")
        print(pd.crosstab(
            df["answer_type"].fillna("<MISSING>"),
            df["correct"].fillna("<MISSING>"),
        ).to_string())

    print("\n=== CHRONOLOGY ===")
    numeric_order = pd.to_numeric(df["order_id"], errors="coerce")
    print("Non-numeric order IDs:", int(numeric_order.isna().sum()))
    print("Duplicate order IDs:", int(df["order_id"].duplicated().sum()))
    print("Minimum order ID:", numeric_order.min())
    print("Maximum order ID:", numeric_order.max())


if __name__ == "__main__":
    main()
