"""Prospective *draft* feasibility sample-size and efficacy-power sensitivity.

This script contains NO participant data and is not a recruitment decision.
It deliberately distinguishes a feasibility pilot's completion-rate precision
from the much larger sample needed to test two independent efficacy contrasts.

For nominal 90 enrolled (30 A/B/C), target 75 completers (25 each),
the per-arm target is NOT guaranteed. Its probability is modeled using a
binomial independent attrition assumption and sensitivity scenarios.

The efficacy calculation reuses the pre-existing exact noncentral-t model
with two A-versus-control Bonferroni comparisons. This is NOT the adjusted
ANCOVA, bounded 16-item endpoint, clustered session analysis, or M-VAS
noninferiority sample size; a statistician and PI must approve the design.

Usage, in agent2_realdata_benchmark:
  python -m scripts.pilot_sample_size_justification
  python -m scripts.pilot_sample_size_justification --completion-probability .75
"""
from __future__ import annotations

import argparse
import json
from math import ceil, isfinite

from scipy.stats import binom

from .pilot_power_analysis import (
    min_detectable_d, min_n_per_arm, two_sample_t_power, wilson_ci,
)

SCHEMA = "IJCAI2027_SAMPLE_SIZE_SENSITIVITY_V1_NOT_APPROVED"


def probability_all_arms_reach_target(
    assigned_per_arm: int, target_per_arm: int,
    completion_probability: float, *, arms: int = 3,
) -> float:
    """Exact probability in the independent, common-p binomial model.

    This is NOT an assurance bound if retention is heterogeneous or clustered,
    and not a guarantee that the overall target will be achieved.
    """
    if (type(assigned_per_arm) is not int or assigned_per_arm < 1
            or type(target_per_arm) is not int or target_per_arm < 1
            or target_per_arm > assigned_per_arm
            or type(arms) is not int or arms < 2
            or not isfinite(completion_probability)
            or not 0 < completion_probability <= 1):
        raise ValueError("invalid balanced binomial completion scenario")
    single = binom.sf(target_per_arm - 1, assigned_per_arm, completion_probability)
    return float(single**arms)


def min_allocated_per_arm(
    target_per_arm: int, completion_probability: float,
    assurance_probability: float, *, arms: int = 3,
    maximum_per_arm: int = 1000,
) -> int:
    """Illustrative enrollment quota if independent completion model were true."""
    if (type(target_per_arm) is not int or target_per_arm < 1
            or not isfinite(completion_probability)
            or not 0 < completion_probability <= 1
            or not isfinite(assurance_probability)
            or not 0 < assurance_probability < 1
            or type(arms) is not int or arms < 2
            or type(maximum_per_arm) is not int
            or maximum_per_arm < target_per_arm):
        raise ValueError("invalid completion assurance parameters")
    for n in range(target_per_arm, maximum_per_arm + 1):
        if probability_all_arms_reach_target(
            n, target_per_arm, completion_probability, arms=arms,
        ) >= assurance_probability:
            return n
    raise ValueError("target assurance not reached within maximum enrollment")


def hypothetical_wilson(k: int, n: int) -> dict:
    lo, hi = wilson_ci(k, n)
    return {
        "hypothetical_successes_if_observed": k,
        "denominator": n,
        "proportion": k / n,
        "wilson_95pct_low": lo,
        "wilson_95pct_high": hi,
        "maximum_distance_from_point_estimate": max(k / n - lo, hi - k / n),
        "is_human_study_result": False,
    }


def planning_report(
    assigned_per_arm: int = 30, target_per_arm: int = 25,
    completion_probability: float = 5 / 6,
    effect_sizes: tuple[float, ...] = (.3, .4, .5, .6, .8, .9),
    family_alpha: float = .05, comparisons: int = 2,
    target_power: float = .8,
) -> dict:
    if (type(assigned_per_arm) is not int or type(target_per_arm) is not int
            or not 3 <= target_per_arm <= assigned_per_arm
            or not isfinite(completion_probability)
            or not 0 < completion_probability <= 1
            or not isfinite(family_alpha)
            or not 0 < family_alpha < 1
            or type(comparisons) is not int or comparisons < 1
            or not isfinite(target_power)
            or not 0 < target_power < 1
            or not effect_sizes
            or any(not isfinite(d) or d <= 0 or d > 2 for d in effect_sizes)):
        raise ValueError("invalid sample-size scenario assumptions")
    arms = 3
    alpha_per_contrast = family_alpha / comparisons
    p_single = float(binom.sf(target_per_arm - 1, assigned_per_arm,
                              completion_probability))
    p_all = probability_all_arms_reach_target(
        assigned_per_arm, target_per_arm, completion_probability,
    )
    expected_total = arms * assigned_per_arm * completion_probability
    target_total = arms * target_per_arm
    scenarios = []
    for d in effect_sizes:
        n = min_n_per_arm(d, target_power=target_power,
                          alpha=alpha_per_contrast)
        scenarios.append({
            "standardized_mean_difference_d": d,
            "power_at_target_completers_per_arm": two_sample_t_power(
                target_per_arm, d, alpha=alpha_per_contrast,
            ),
            "required_completers_per_arm_for_target_power": n,
            "illustrative_total_recruits_at_assumed_completion": (
                arms * ceil(n / completion_probability)
            ),
        })
    return {
        "schema_version": SCHEMA,
        "study_mode": "UNDECIDED_PROSPECTIVE_FEASIBILITY_VERSUS_DEFINITIVE_EFFICACY",
        "recommended_current_scope": "FEASIBILITY_PILOT_CANDIDATE_REQUIRES_PI_STATISTICIAN_APPROVAL",
        "human_enrollment_authorized": False,
        "sample_size_approved": False,
        "uses_real_student_data": False,
        "primary_pilot_objective": "feasibility_recruitment_retention_and_measurement",
        "model": {
            "assignment": "three exactly balanced arms, independent individuals",
            "completions": "independent Bernoulli with same assumed probability in all arms",
            "completion_probability_assumed": completion_probability,
            "recruitment_time_site_cluster_effects_modeled": False,
            "efficacy_sensitivity": "two-sided equal-variance independent unadjusted t tests",
            "efficacy_alpha_per_comparison_bonferroni": alpha_per_contrast,
            "number_of_A_vs_control_comparisons": comparisons,
            "target_efficacy_power": target_power,
            "adjustment_for_pretest_or_ceiling": False,
            "fatigue_noninferiority_power_calculated": False,
        },
        "nominal_enrollment": {
            "assigned_per_arm": assigned_per_arm,
            "total_enrolled": arms * assigned_per_arm,
            "target_completers_per_arm": target_per_arm,
            "target_completers_total": target_total,
            "expected_completers_total_under_model": expected_total,
            "probability_one_arm_reaches_target": p_single,
            "probability_all_three_arms_reach_target": p_all,
            "probability_total_reaches_target": float(
                binom.sf(target_total - 1, arms * assigned_per_arm,
                         completion_probability)
            ),
            "completion_interval_overall_if_exact_target_observed":
                hypothetical_wilson(target_total, arms * assigned_per_arm),
            "completion_interval_one_arm_if_exact_target_observed":
                hypothetical_wilson(target_per_arm, assigned_per_arm),
        },
        "assurance_scenarios_if_independent_model_were_correct": [
            {
                "minimum_assigned_per_arm": n,
                "total_enrollment": arms * n,
                "target_completers_each_arm": target_per_arm,
                "required_probability_all_three_arms": assurance,
                "achieved_modeled_probability": probability_all_arms_reach_target(
                    n, target_per_arm, completion_probability,
                ),
            }
            for assurance in (.8, .9, .95)
            for n in [min_allocated_per_arm(
                target_per_arm, completion_probability, assurance
            )]
        ],
        "effect_size_sensitivity_only": scenarios,
        "minimum_detectable_d_at_nominal_completers": min_detectable_d(
            target_per_arm, target_power=target_power, alpha=alpha_per_contrast,
        ),
        "decisions_before_first_real_student": [
            "PI and statistician choose feasibility pilot or definitive hypothesis-testing RCT",
            "Approve the pilot primary feasibility outcome, precision, and progression criteria",
            "Approve expected attrition using real recruitment/retention evidence",
            "If confirmatory: prespecify minimum meaningful difference on 0-16 posttest, pooled residual variance, baseline correlation, analysis model and multiplicity",
            "Check classroom/site/instructor clustering, differential missingness, finite sampling frame, allocation, power and schedule capacity",
            "If noninferiority claim about fatigue: define defensible margin and power that estimand separately",
            "Freeze and sign dated protocol/SAP/sample-size memo before unblinding or recruitment",
        ],
        "disclaimer": (
            "DESIGN SENSITIVITY ONLY; no approval or recruitment authority. "
            "Modeled retention is not guaranteed, treatment effects are "
            "not measured, and sample size may change with approved design."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assigned-per-arm", type=int, default=30)
    parser.add_argument("--target-completers-per-arm", type=int, default=25)
    parser.add_argument("--completion-probability", type=float, default=5 / 6)
    parser.add_argument("--effect-sizes", default="0.3,0.4,0.5,0.6,0.8,0.9")
    parser.add_argument("--family-alpha", type=float, default=.05)
    parser.add_argument("--comparisons", type=int, default=2)
    parser.add_argument("--target-power", type=float, default=.8)
    args = parser.parse_args()
    try:
        effects = tuple(float(s.strip()) for s in args.effect_sizes.split(","))
        report = planning_report(
            assigned_per_arm=args.assigned_per_arm,
            target_per_arm=args.target_completers_per_arm,
            completion_probability=args.completion_probability,
            effect_sizes=effects,
            family_alpha=args.family_alpha,
            comparisons=args.comparisons,
            target_power=args.target_power,
        )
    except ValueError as error:
        parser.exit(2, "Invalid PROSPECTIVE power scenario: " + str(error) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
