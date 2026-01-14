#!/usr/bin/env python3
"""
src.inspect_artifacts

Small utility to print shapes and counts for demo purposes.
Avoids bash heredocs during live demos.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    q = np.load("data/synth/Q.npy")
    q_cb = np.load("data/synth/Q_CB.npy")
    item_index = json.loads(Path("data/synth/item_index.json").read_text(encoding="utf-8"))

    print("Q.npy    shape:", q.shape)
    print("Q_CB.npy shape:", q_cb.shape)
    print("num_items:", len(item_index))

    logs = Path("data/synth/logs_synth.csv")
    if logs.exists():
        df = pd.read_csv(logs)
        print("logs_synth.csv rows:", len(df))

    logs_seq = Path("data/synth/logs_seq.csv")
    if logs_seq.exists():
        df = pd.read_csv(logs_seq)
        print("logs_seq.csv rows:", len(df), "| columns:", list(df.columns))

    logs_seq_bloom = Path("data/synth/logs_seq_bloom.csv")
    if logs_seq_bloom.exists():
        df = pd.read_csv(logs_seq_bloom)
        print("logs_seq_bloom.csv rows:", len(df), "| columns:", list(df.columns))


if __name__ == "__main__":
    main()

