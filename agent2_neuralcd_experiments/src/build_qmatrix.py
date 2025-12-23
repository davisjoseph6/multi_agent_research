#!/usr/bin/env python3
"""
Build Q-matrix (M x K) and Bloom-aware Q_CB (M x (K*B)) from item metadata.
"""
import json
from pathlib import Path
import numpy as np


def build_q_matrices(taxonomy_path: str, items_path: str, out_dir: str) -> None:
    tax = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    items = json.loads(Path(items_path).read_text(encoding="utf-8"))["items"]

    concepts = [c["concept_id"] for c in tax["concepts"]]
    blooms = [b["bloom_id"] for b in tax["bloom_levels"]]

    c2i = {cid: i for i, cid in enumerate(concepts)}
    b2i = {bid: i for i, bid in enumerate(blooms)}

    M, K, B = len(items), len(concepts), len(blooms)

    Q = np.zeros((M, K), dtype=np.float32)
    Q_CB = np.zeros((M, K * B), dtype=np.float32)

    item_index = {}
    for m, it in enumerate(items):
        item_id = it["item_id"]
        item_index[item_id] = m
        for cid in it["concept_ids"]:
            Q[m, c2i[cid]] = 1.0
            # Bloom-aware: activate only the Bloom column for that concept
            b = b2i[it["bloom_id"]]
            Q_CB[m, c2i[cid] * B + b] = 1.0

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "Q.npy", Q)
    np.save(out / "Q_CB.npy", Q_CB)

    (out / "item_index.json").write_text(json.dumps(item_index, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build_q_matrices(
        "data/taxonomy/thermo_v0.taxonomy.json",
        "data/items/thermo_v0.items.json",
        "data/synth"
    )

