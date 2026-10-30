"""Run a fail-closed, small, exact path-oracle parity probe (no held-out data)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from src.prototype.step95_bayesian_forgetting_filter import (
    Model, compare_forgetting_models, stream,
)
from scripts.step95_filter_path_oracle import enumerate_paths


def probe() -> dict:
    rows = []
    max_error = 0.0
    for label, responses, learning in (
        ("CCWW", (True, True, False, False), (0, 0, 0, 0)),
        ("missing", (True, None, False, True), (.05, .05, 0, .1)),
        ("mixed", (False, True, False, None, True), (.1, .2, 0, .3, .1)),
    ):
        model = Model(slip=.1, guess=.25, forget=.02)
        actual = stream(model, responses, learning, initial_mastery=.75)
        oracle = enumerate_paths(responses, learning, initial_mastery=.75,
                                 slip=.1, guess=.25, forget=.02)
        mappings = (
            ("prior_mastery", "prior_mastery"),
            ("posterior_mastery", "posterior_mastery"),
            ("posterior_recent_forgetting", "recent_forgetting_posterior"),
            ("predictive_next_mastery", "predictive_next_mastery"),
            ("observation_likelihood", "observation_likelihood"),
            ("cumulative_log_likelihood", "cumulative_log_likelihood"),
        )
        for a, o in zip(actual, oracle):
            for field, oracle_field in mappings:
                error = abs(getattr(a, field) - getattr(o, oracle_field))
                max_error = max(max_error, error)
                if error > 2e-12:
                    raise AssertionError(f"{label}: {field} error {error}")
        rows.append({
            "name": label,
            "observations": len(responses),
            "posterior_mastery": actual[-1].posterior_mastery,
            "posterior_recent_forgetting": actual[-1].posterior_recent_forgetting,
            "cumulative_log_likelihood": actual[-1].cumulative_log_likelihood,
        })
    h1 = compare_forgetting_models((True, True, False, False), (0,) * 4,
                                   initial_mastery=.75, alternative_forgetting=.02)
    path = Path(__file__).resolve().parents[1] / "src/prototype/step95_bayesian_forgetting_filter.py"
    return {
        "verification_scope": "short-path mathematical parity only",
        "original_filter_source_sha256": sha256(path.read_bytes()).hexdigest(),
        "independent_oracle": "enumeration of all hidden mastery trajectories",
        "max_absolute_error": max_error,
        "probe_cases": rows,
        "CCWW_H1_posterior": h1.posterior_probability_of_forgetting_model,
        "heldout_seeds_accessed": False,
        "human_evidence": False,
        "algorithmic_novelty_established": False,
        "note": "Correct filtering equations do not validate model parameters or educational effectiveness.",
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
