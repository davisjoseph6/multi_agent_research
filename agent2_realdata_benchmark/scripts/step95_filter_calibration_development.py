"""Independent two-state HMM calibration benchmark (DEVELOPMENT ONLY).

This is a standalone reference, intentionally NOT a replacement for the
repository's step95_bayesian_forgetting_filter.TwoStateFilter. It can help
falsify calibration claims but cannot validate a cognitive model with humans.

Time: state S[t] -> response Y[t] -> action transition -> state S[t+1].
Every action uses a constant specified learning rate in this controlled audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
import math
import random
from statistics import mean
from typing import Sequence

DEV_START = 120000
HELDOUT_START = 200000


@dataclass(frozen=True)
class Rates:
    forget: float
    learn: float
    slip: float
    guess: float = .25
    initial_mastery: float = .75

    def __post_init__(self):
        for name in ("forget", "learn", "slip", "guess", "initial_mastery"):
            value = getattr(self, name)
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and in [0,1]")


# Model assumptions are fixed here and must not be tuned on held-out data.
WORLDS = {
    "stationary": Rates(forget=0.0, learn=.05, slip=.10),
    "slow_forgetting": Rates(forget=.02, learn=.05, slip=.10),
    "rapid_forgetting": Rates(forget=.08, learn=.05, slip=.10),
    "noisy_forgetting": Rates(forget=.02, learn=.05, slip=.25),
}


@dataclass(frozen=True)
class FilterOutput:
    mastery_prior: float
    response_prediction: float
    mastery_posterior: float
    last_transition_forgetting_posterior: float | None


class ReferenceFilter:
    """Exact two-state filter with event posterior and explicit time convention."""

    def __init__(self, rates: Rates):
        self.rates = rates
        self.prior = rates.initial_mastery
        self.previous_posterior = None

    def step(self, response: bool | None) -> FilterOutput:
        if response is not None and type(response) is not bool:
            raise ValueError("response must be bool or None")
        r = self.rates
        pred = self.prior * (1 - r.slip) + (1 - self.prior) * r.guess
        likelihood1 = 1.0 if response is None else (1 - r.slip if response else r.slip)
        likelihood0 = 1.0 if response is None else (r.guess if response else 1 - r.guess)
        evidence = self.prior * likelihood1 + (1 - self.prior) * likelihood0
        if evidence <= 0:
            raise ValueError("Observation impossible under assumed model")
        posterior = self.prior * likelihood1 / evidence
        event = None
        if self.previous_posterior is not None:
            event = self.previous_posterior * r.forget * likelihood0 / evidence
        result = FilterOutput(self.prior, pred, posterior, event)
        self.previous_posterior = posterior
        self.prior = posterior * (1 - r.forget) + (1 - posterior) * r.learn
        return result


def uniform(seed: int, time: int, event: str) -> float:
    if type(seed) is not int or not DEV_START <= seed < HELDOUT_START:
        raise ValueError("Only development seeds are authorized")
    data = f"step95-calibration-v1|{seed}|{time}|{event}".encode()
    return int.from_bytes(sha256(data).digest()[:8], "big") / (1 << 64)


def simulate(world: Rates, seed: int, horizon: int) -> list[tuple[bool, bool, bool]]:
    """Return (true S_t, observed Y_t, F_(t-1)); time-0 event always False."""
    if type(horizon) is not int or not 2 <= horizon <= 200:
        raise ValueError("horizon must be 2..200")
    state = uniform(seed, -1, "initial") < world.initial_mastery
    out = []
    forgot = False
    for t in range(horizon):
        p_y = (1 - world.slip) if state else world.guess
        y = uniform(seed, t, "response") < p_y
        out.append((state, y, forgot))
        if state:
            forgot = uniform(seed, t, "forget") < world.forget
            state = not forgot
        else:
            state = uniform(seed, t, "learn") < world.learn
            forgot = False
    return out


def one_run(world: Rates, assumed: Rates, seed: int, horizon: int) -> list[dict]:
    ref = ReferenceFilter(assumed)
    records = []
    for t, (state, y, forgot) in enumerate(simulate(world, seed, horizon)):
        estimate = ref.step(y)
        records.append({
            "t": t,
            "response_correct": int(y),
            "true_mastered": int(state),
            "true_last_forgetting": int(forgot),
            "pred_correct": estimate.response_prediction,
            "mastery_posterior": estimate.mastery_posterior,
            "forgetting_posterior": estimate.last_transition_forgetting_posterior,
        })
    return records


def brier(p: float, actual: int) -> float:
    return (p - actual) ** 2


def log_loss(p: float, actual: int) -> float:
    # Avoid a runtime exception for a decisively impossible observation.
    # This is numerical clipping, not a claim of model correctness.
    p = max(1e-15, min(1 - 1e-15, p))
    return -(math.log(p) if actual else math.log1p(-p))


def calibration_bins(records: Sequence[dict], p_key: str, y_key: str) -> list[dict]:
    buckets = [[] for _ in range(10)]
    for r in records:
        p = r[p_key]
        buckets[min(9, int(p * 10))].append((p, r[y_key]))
    return [
        {"bin": i, "count": len(bucket),
         "mean_predicted": mean(p for p, _ in bucket),
         "mean_observed": mean(y for _, y in bucket)}
        for i, bucket in enumerate(buckets) if bucket
    ]


def score(records: Sequence[dict]) -> dict:
    if not records:
        raise ValueError("No records")
    event_records = [r for r in records if r["forgetting_posterior"] is not None]
    result = {
        "n_responses": len(records),
        "response_prequential_brier": mean(brier(r["pred_correct"], r["response_correct"]) for r in records),
        "response_prequential_log_loss": mean(log_loss(r["pred_correct"], r["response_correct"]) for r in records),
        "hidden_mastery_post_brier_oracle_only": mean(brier(r["mastery_posterior"], r["true_mastered"]) for r in records),
        "hidden_transition_post_brier_oracle_only": mean(brier(r["forgetting_posterior"], r["true_last_forgetting"]) for r in event_records),
        "empirical_forgetting_event_rate": mean(r["true_last_forgetting"] for r in event_records),
        "mean_predicted_forgetting_event_rate": mean(r["forgetting_posterior"] for r in event_records),
        "response_calibration_bins": calibration_bins(records, "pred_correct", "response_correct"),
        "mastery_calibration_bins_oracle_only": calibration_bins(records, "mastery_posterior", "true_mastered"),
        "forgetting_event_calibration_bins_oracle_only": calibration_bins(event_records, "forgetting_posterior", "true_last_forgetting"),
    }
    result["response_expected_calibration_error_descriptive"] = sum(
        (b["count"] / len(records)) * abs(b["mean_predicted"] - b["mean_observed"])
        for b in result["response_calibration_bins"]
    )
    return result


def paired_bootstrap(values: Sequence[float], bootstrap_seed: int = 79013, repetitions: int = 1000) -> dict:
    """Percentile interval over independent synthetic learner seeds, not items."""
    if not values:
        raise ValueError("At least one seed is required")
    n = len(values)
    if n == 1:
        return {"paired_seed_mean": values[0], "descriptive_95pct_interval": [values[0], values[0]],
                "independent_units": "synthetic_learner_seed", "n_seeds": 1}
    rng = random.Random(bootstrap_seed)
    distribution = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(repetitions))
    return {"paired_seed_mean": mean(values),
            "descriptive_95pct_interval": [distribution[int(.025*(repetitions-1))],
                                              distribution[int(.975*(repetitions-1))]],
            "independent_units": "synthetic_learner_seed", "n_seeds": n}


def benchmark(world_name: str, participants: int = 300, horizon: int = 30) -> dict:
    if world_name not in WORLDS or type(participants) is not int or not 1 <= participants <= 3000:
        raise ValueError("Invalid world or number of development participants")
    if type(horizon) is not int or not 2 <= horizon <= 200:
        raise ValueError("Invalid horizon")
    world = WORLDS[world_name]
    models = {
        "oracle_parameters": world,
        "nominal_forgetting": Rates(.02, .05, .10),
        "stationary_no_forgetting": Rates(0, .05, .10),
        "high_forgetting": Rates(.10, .05, .10),
        "wrong_observation_slip": Rates(.02, .05, .25 if world.slip == .10 else .10),
    }
    results = {}
    seed_level_response_brier = {}
    for label, assumed in models.items():
        rows = []
        losses_by_seed = []
        for seed in range(DEV_START, DEV_START + participants):
            one = one_run(world, assumed, seed, horizon)
            rows.extend(one)
            losses_by_seed.append(mean(brier(r["pred_correct"], r["response_correct"]) for r in one))
        results[label] = score(rows)
        seed_level_response_brier[label] = losses_by_seed
    comparisons = {
        f"oracle_minus_{label}_response_brier": paired_bootstrap([
            x - y for x,y in zip(seed_level_response_brier["oracle_parameters"],
                              seed_level_response_brier[label])
        ])
        for label in models if label != "oracle_parameters"
    }
    manifest = {
        "world": world_name, "world_rates": world.__dict__,
        "models": {k: v.__dict__ for k, v in models.items()},
        "participants": participants, "horizon": horizon,
        "development_seed_start": DEV_START,
        "development_seed_end_inclusive": DEV_START + participants - 1,
        "heldout_seeds_accessed": False,
        "simulation_time_convention": "S_t -> Y_t -> independent learn/forget transition -> S_t+1",
    }
    return {
        "manifest": manifest,
        "manifest_sha256": sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "synthetic_only": True, "human_evidence": False,
        "reference_is_independent_of_existing_filter_source": True,
        "summary": results,
        "paired_oracle_comparisons": comparisons,
        "disclaimer": "In-simulator oracle labels; no human calibration, novel method, or decision-policy benefit established.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", choices=("all", *WORLDS), default="slow_forgetting")
    parser.add_argument("--participants", type=int, default=300)
    parser.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args()
    worlds = WORLDS if args.world == "all" else (args.world,)
    print(json.dumps({name: benchmark(name, args.participants, args.horizon) for name in worlds}, indent=2))


if __name__ == "__main__":
    main()
