"""Run existing draft-bank inventory certificate; no files modified."""
from pathlib import Path
import json
from src.prototype.step98_finite_inventory_certificate import demo_bank_snapshots


def main():
    path = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1/items.csv"
    report = demo_bank_snapshots(path)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
