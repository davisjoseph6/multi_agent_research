"""Preliminary two-arm sensitivity for the *three-arm* feasibility pilot.

Interpretation: two planned comparisons A-B and A-C; two-sided Bonferroni
per-comparison alpha=.025 if family alpha=.05. Simple unadjusted equal-variance
independent t-test, *not* ANCOVA/repeated-measures power. Participants, not
sessions, are randomized units. Pilot feasibility is the primary study purpose.

Usage:
python -m scripts.pilot_power_analysis --completers-per-arm 25 \
    --effect-sizes 0.3,0.4,0.5,0.6,0.8,0.9

No participant data accessed or modified.
"""
from __future__ import annotations

import argparse
import json
import math

from scipy.stats import nct, norm, t


def two_sample_t_power(n_per_arm: int, d: float, *, alpha: float = 0.025) -> float:
    """Exact noncentral-t two-sided power, equal sample sizes and variances."""
    if type(n_per_arm) is not int or n_per_arm < 3:
        raise ValueError("n_per_arm must be an integer >=3")
    if not math.isfinite(d) or d < 0 or not 0 < alpha < 1:
        raise ValueError("d must be >=0, alpha must be (0,1)")
    df = 2 * n_per_arm - 2
    t_critical = t.ppf(1 - alpha / 2, df)
    noncentrality = d * math.sqrt(n_per_arm / 2)
    result = nct.sf(t_critical, df, noncentrality) + nct.cdf(-t_critical, df, noncentrality)
    if not math.isfinite(result):
        raise ArithmeticError("noncentral t power failed; do not silently substitute an estimate")
    return float(result)


def min_n_per_arm(d: float, target_power: float = 0.80, *,
                  alpha: float = 0.025, upper_limit: int = 5000) -> int:
    if not 0 < target_power < 1:
        raise ValueError("target_power must be between 0 and 1")
    for n in range(3, upper_limit + 1):
        if two_sample_t_power(n, d, alpha=alpha) >= target_power:
            return n
    raise ValueError("target power not reached in configured range")


def min_detectable_d(n_per_arm: int, *, target_power: float = 0.80,
                     alpha: float = 0.025) -> float:
    """Bisection robust to noncentral-t numeric overflow at extreme d."""
    lo, hi = 0.0, 1.0
    while two_sample_t_power(n_per_arm, hi, alpha=alpha) < target_power:
        hi *= 1.25
        if hi >= 2:
            raise ValueError("target power unattainable within d<=2")
    for _ in range(48):
        mid = (lo + hi) / 2
        if two_sample_t_power(n_per_arm, mid, alpha=alpha) >= target_power:
            hi = mid
        else:
            lo = mid
    return hi


def wilson_ci(successes: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if not 0 <= successes <= total or total < 1 or not 0 < alpha < 1:
        raise ValueError("invalid count or alpha")
    z = norm.ppf(1 - alpha / 2)
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total ** 2)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completers-per-arm", type=int, default=25)
    parser.add_argument("--recruited-per-arm", type=int, default=30)
    parser.add_argument("--family-alpha", type=float, default=0.05)
    parser.add_argument("--two-planned-contrasts", type=int, default=2)
    parser.add_argument("--target-power", type=float, default=0.8)
    parser.add_argument("--attrition-rate", type=float, default=1 / 6)
    parser.add_argument("--effect-sizes", default="0.3,0.4,0.5,0.6,0.8,0.9")
    args = parser.parse_args()
    if not 0 <= args.attrition_rate < 1:
        parser.error("attrition-rate must be in [0,1)")
    if args.two_planned_contrasts < 1 or not 0 < args.family_alpha < 1:
        parser.error("invalid comparisons or family-alpha")
    if args.recruited_per_arm < args.completers_per_arm:
        parser.error("recruited-per-arm must be >= completers-per-arm")
    effect_sizes = [float(s) for s in args.effect_sizes.split(",")]
    alpha = args.family_alpha / args.two_planned_contrasts
    expected_rate = args.completers_per_arm / args.recruited_per_arm
    report = {
        "scope": "SENSITIVITY_ONLY_NOT_A_FINAL_RCT_POWER_JUSTIFICATION",
        "assumptions": {
            "design": "2 independent equal-variance equal-size samples per planned contrast",
            "test": "two-sided noncentral-t",
            "primary_outcome_scale": "candidate 16-item posttest; d uses unadjusted pooled SD",
            "ancova_covariates_accounted_for": False,
            "clustering_and_repeated_measures_accounted_for": False,
            "arms": 3,
            "planned_A_vs_control_contrasts": args.two_planned_contrasts,
            "bonferroni_alpha_per_comparison": alpha,
            "target_power": args.target_power,
            "attrition_fraction_assumed": args.attrition_rate
        },
        "nominal_target": {
            "randomized": 3 * args.recruited_per_arm,
            "completers": 3 * args.completers_per_arm,
            "completion_proportion": expected_rate,
            "wilson_95pct_completion_interval_if_observed": wilson_ci(
                3 * args.completers_per_arm, 3 * args.recruited_per_arm),
            "minimum_detectable_standardized_d_at_target_power": min_detectable_d(
                args.completers_per_arm, target_power=args.target_power, alpha=alpha)
        },
        "effect_size_sensitivity": [
            {
                "d": d,
                "power_at_nominal_completers": two_sample_t_power(
                    args.completers_per_arm, d, alpha=alpha),
                "required_completers_per_arm": (n := min_n_per_arm(
                    d, target_power=args.target_power, alpha=alpha)),
                "approx_recruits_total_balanced_arms": 3 * math.ceil(
                    n / (1 - args.attrition_rate))
            }
            for d in effect_sizes
        ],
        "warning": "Pilot feasibility rationale differs from powering a definitive efficacy study. Confirm model, SD, baseline correlation, missingness, ceiling effects and multiplicity with statistician."
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
