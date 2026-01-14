#!/usr/bin/env python3
"""
src.pick_demo_cases

Print candidate (student_idx, t) pairs where delta_t is large,
so you can demo forgetting clearly.
"""
from __future__ import annotations

import argparse

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use_bloom", action="store_true")
    parser.add_argument("--min_gap", type=float, default=20.0)
    parser.add_argument("--top_k", type=int, default=10)
    args = parser.parse_args()

    path = "data/synth/logs_seq_bloom.csv" if args.use_bloom else "data/synth/logs_seq.csv"
    df = pd.read_csv(path)

    big = df[df["delta_t"] >= args.min_gap].sort_values(
        ["delta_t", "student_idx", "t"],
        ascending=[False, True, True],
    )

    print("Using:", path)
    print("Found big gaps:", len(big))

    if len(big) == 0:
        return

    print("\nTop candidates:")
    print(big[["student_idx", "t", "item_idx", "correct", "delta_t"]].head(args.top_k).to_string(index=False))


if __name__ == "__main__":
    main()
