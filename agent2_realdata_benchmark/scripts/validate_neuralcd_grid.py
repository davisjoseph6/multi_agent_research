#!/usr/bin/env python3
"""Prespecified NeuralCD adaptation grid: validation only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import scripts.validate_neuralcd as validator


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/data/neuralcd_grid_spec_v1.json"

LEARNING_RATES = (0.01, 0.1, 0.3)
PENALTIES = (0.0, 0.01, 0.1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def token(value: float) -> str:
    return format(value, "g").replace(".", "p")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--epoch",
        type=int,
        choices=range(1, 6),
        required=True,
    )

    parser.add_argument(
        "--lr",
        type=float,
        choices=LEARNING_RATES,
        required=True,
    )

    parser.add_argument(
        "--penalty",
        type=float,
        choices=PENALTIES,
        required=True,
    )

    parser.add_argument(
        "--max-students",
        type=int,
        default=None,
        help="Integration testing only.",
    )

    args = parser.parse_args()

    if (
        args.max_students is not None
        and args.max_students < 1
    ):
        parser.error("--max-students must be positive")

    if args.lr == 0.1 and args.penalty == 0.01:
        parser.error(
            "The reference configuration already exists in validation_v1."
        )

    specification = json.loads(
        SPEC.read_text(encoding="utf-8")
    )

    if specification["version"] != "neuralcd_grid_v1":
        raise RuntimeError("Incorrect grid specification")

    if sha256(Path(validator.__file__)) != (
        specification["validator_sha256"]
    ):
        raise RuntimeError(
            "Validated driver changed after grid registration"
        )

    if sha256(Path(__file__)) != (
        specification["wrapper_sha256"]
    ):
        raise RuntimeError(
            "Grid wrapper changed after registration"
        )

    candidate = {
        "epoch": args.epoch,
        "learning_rate": args.lr,
        "prior_penalty": args.penalty,
    }

    if candidate not in specification["candidates"]:
        raise RuntimeError(
            "Candidate was not registered before evaluation"
        )

    name = (
        f"lr{token(args.lr)}_"
        f"pen{token(args.penalty)}"
    )

    validator.OUTPUT = (
        ROOT
        / "results/neuralcd/validation_grid_v1"
        / name
    )

    validator.ADAPTATION_LR = args.lr
    validator.PRIOR_PENALTY = args.penalty

    forwarded = [
        "validate_neuralcd",
        "--epoch",
        str(args.epoch),
    ]

    if args.max_students is not None:
        forwarded.extend([
            "--max-students",
            str(args.max_students),
        ])

    sys.argv = forwarded

    print(
        "Registered grid candidate:",
        candidate,
        flush=True,
    )

    # Reuse the existing, integrity-checked causal evaluator.
    validator.main()


if __name__ == "__main__":
    main()
