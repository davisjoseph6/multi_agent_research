"""Step101 read-only audit of the frozen Step100 full development JSON.

Refuses altered/mixed source hashes, missing seeds, duplicate policies,
incorrect reward summaries, and incorrect paired bootstrap contrasts.
Does not rerun learners, inspect sealed sets, or authorize human subjects.

From agent2_realdata_benchmark:
  python -m scripts.step101_step100_evidence_audit \
    --input /tmp/ijcai_step100_full_01.json \
    --output /tmp/ijcai_step101_audit_01.json \
    --markdown /tmp/ijcai_step101_audit_01.md
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

from scripts.step100_inventory_policy_comparison import (
    FULL_COUNT, HORIZON, POLICIES, SCENARIOS, SEED_START, SIMULATIONS,
    paired_contrast,
)

SOURCES = (
    "scripts/step100_inventory_policy_comparison.py",
    "src/prototype/step99_inventory_aware_pomcp.py",
    "src/prototype/study_v3_pomcp.py",
    "src/prototype/study_v2.py",
    "docs/step100_inventory_policy_comparison_PLAN.md",
)
CONTRASTS = {
    "primary_step99_vs_v3": ("step99", "v3"),
    "exploratory_step99_vs_greedy": ("step99", "greedy_no_resource"),
    "exploratory_step99_vs_fixed": ("step99", "balanced_fixed_no_resource"),
}
MEAN_FIELDS = {
    "mean_posttest_accuracy": "posttest_accuracy",
    "mean_latent_mastery_diagnostic": "final_latent_mastery_fraction",
    "mean_resource_actions": "resource_actions",
    "mean_nominal_cost": "nominal_action_cost",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def same_number(a: object, b: object) -> bool:
    return (type(a) in (int, float) and type(b) in (int, float)
            and math.isfinite(a) and math.isfinite(b)
            and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10))


def verify(report: dict, *, root: Path = Path(".")) -> dict:
    require(type(report) is dict, "Expected JSON object")
    require(report.get("status") == "EXPLORATORY_DEVELOPMENT_ONLY; NO_STUDENT_EFFICACY"
            and report.get("quick_smoke_only") is False,
            "Only the FULL synthetic development report is eligible")
    require(report.get("human_participants") is False
            and report.get("heldout_data_accessed") is False
            and report.get("can_establish_ai_novelty") is False
            and report.get("original_ijcai_rct_unchanged") is True,
            "Development-only safety and validity metadata missing")

    manifest = report.get("manifest", {})
    require(type(manifest) is dict
            and manifest.get("study") == "step100_paired_finite_inventory_dev_v1"
            and manifest.get("seeds") == list(range(SEED_START, SEED_START + FULL_COUNT))
            and manifest.get("policies") == list(POLICIES)
            and manifest.get("scenarios") == list(SCENARIOS)
            and manifest.get("planner_simulations") == SIMULATIONS
            and manifest.get("horizon") == HORIZON
            and manifest.get("practice_session_quotas") == [20, 20, 15]
            and manifest.get("resource_slots_per_session") == 2,
            "Unexpected Step100 full-run protocol or seed manifest")

    digests = report.get("source_sha256")
    require(type(digests) is dict and set(digests) == set(SOURCES),
            "Source fingerprint set missing or changed")
    for source in SOURCES:
        file = root / source
        require(file.is_file(), f"Source absent: {source}")
        require(sha256(file.read_bytes()).hexdigest() == digests[source],
                f"Source changed after evaluation: {source}")

    rows = report.get("episodes")
    require(type(rows) is list
            and len(rows) == len(SCENARIOS) * FULL_COUNT * len(POLICIES),
            "Missing or duplicate total episode count")
    expected = {(s, seed, p) for s in SCENARIOS
                for seed in range(SEED_START, SEED_START + FULL_COUNT)
                for p in POLICIES}
    observed = []
    for row in rows:
        require(type(row) is dict, "Malformed episode")
        key = (row.get("scenario"), row.get("seed"), row.get("policy"))
        observed.append(key)
        require(row.get("synthetic_only") is True,
                "Real student flag or missing fictional marker")
        question = row.get("practice_answers")
        resources = row.get("resource_actions")
        steps = row.get("total_actions")
        correct = row.get("posttest_correct_of_16")
        accuracy = row.get("posttest_accuracy")
        mastery = row.get("final_latent_mastery_fraction")
        cost = row.get("nominal_action_cost")
        by_kind = row.get("resources_by_kind")
        require(type(question) is int and question == 55
                and type(resources) is int and 0 <= resources <= 6
                and type(steps) is int and steps == question + resources,
                "Invalid practice/resource/step accounting")
        require(type(correct) is int and 0 <= correct <= 16
                and same_number(accuracy, correct / 16)
                and same_number(mastery, mastery)
                and 0 <= mastery <= 1
                and same_number(cost, cost) and cost >= 0,
                "Invalid posttest/latent/cost data")
        require(type(by_kind) is dict
                and all(isinstance(kind, str) and type(n) is int and n >= 0
                        for kind, n in by_kind.items())
                and sum(by_kind.values()) == resources,
                "Resource composition does not reconcile")
        if row.get("policy", "").endswith("_no_resource"):
            require(resources == 0, "No-resource baseline received assistance")
    require(len(set(observed)) == len(observed) and set(observed) == expected,
            "Missing/duplicated scenario, policy, or development seed")

    original_means = report.get("policy_means")
    original_contrasts = report.get("contrasts")
    require(type(original_means) is dict and set(original_means) == set(SCENARIOS)
            and type(original_contrasts) is dict
            and set(original_contrasts) == set(SCENARIOS),
            "Missing scenario summaries")

    primary = {}
    policy_dose = {}
    for scenario in SCENARIOS:
        require(set(original_means[scenario]) == set(POLICIES)
                and set(original_contrasts[scenario]) == set(CONTRASTS),
                f"Unregistered comparison in {scenario}")
        dose = {}
        for policy in POLICIES:
            policy_rows = [r for r in rows
                           if r["scenario"] == scenario and r["policy"] == policy]
            expected_means = {
                out: mean(r[source] for r in policy_rows)
                for out, source in MEAN_FIELDS.items()
            }
            summary = original_means[scenario][policy]
            require(type(summary) is dict
                    and set(summary) == set(MEAN_FIELDS),
                    f"Invalid policy summary: {scenario}/{policy}")
            for name, expected_value in expected_means.items():
                require(same_number(summary[name], expected_value),
                        f"Policy average mismatch: {scenario}/{policy}/{name}")
            dose[policy] = {
                "mean_recovery_resources": expected_means["mean_resource_actions"],
                "mean_nominal_cost": expected_means["mean_nominal_cost"],
                "mean_posttest_accuracy": expected_means["mean_posttest_accuracy"],
            }
        policy_dose[scenario] = dose
        for name, (first, second) in CONTRASTS.items():
            computed = paired_contrast(rows, first, second, scenario)
            saved = original_contrasts[scenario][name]
            require(type(saved) is dict
                    and set(saved) == set(computed)
                    and saved["paired_development_seeds"] == FULL_COUNT
                    and saved["wins_ties_losses"] == computed["wins_ties_losses"]
                    and saved["contrast"] == computed["contrast"]
                    and saved["interpretation"] == computed["interpretation"],
                    f"Paired contrast metadata mismatch: {scenario}/{name}")
            require(same_number(saved["mean_posttest_accuracy_difference"],
                                computed["mean_posttest_accuracy_difference"]),
                    f"Paired contrast mean mismatch: {scenario}/{name}")
            a = saved["descriptive_seed_bootstrap_95pct"]
            b = computed["descriptive_seed_bootstrap_95pct"]
            require(type(a) is list and len(a) == 2
                    and all(same_number(x, y) for x, y in zip(a, b)),
                    f"Paired contrast bootstrap mismatch: {scenario}/{name}")
            if name == "primary_step99_vs_v3":
                primary[scenario] = {
                    "mean_difference": computed["mean_posttest_accuracy_difference"],
                    "descriptive_interval": computed["descriptive_seed_bootstrap_95pct"],
                    "wins_ties_losses": computed["wins_ties_losses"],
                }

    all_positive = all(v["mean_difference"] > 0 for v in primary.values())
    all_lower_positive = all(v["descriptive_interval"][0] > 0 for v in primary.values())
    return {
        "status": "READ_ONLY_VALIDATED_FULL_STEP100_DEVELOPMENT_ONLY",
        "verified_episode_count": len(rows),
        "paired_development_seeds_per_scenario": FULL_COUNT,
        "source_fingerprints_verified": True,
        "human_study_authorized": False,
        "human_learning_effect_established": False,
        "algorithmic_novelty_established": False,
        "broad_step99_superiority_established": False,
        "primary_scenario_results": primary,
        "resource_dose_and_cost_diagnostics": policy_dose,
        "all_primary_means_positive": all_positive,
        "all_primary_descriptive_lower_limits_positive": all_lower_positive,
        "screening_outcome": (
            "DESCRIPTIVELY_POSITIVE_ONLY_NOT_CONFIRMATORY"
            if all_positive and all_lower_positive else
            "NO_GO_FOR_BROAD_STEP99_SUPERIORITY_CLAIM"
        ),
        "limitations": [
            "Source-calculated synthetic learner dynamics are assumed, not measured.",
            "This is an exploratory development comparison, not independent confirmation.",
            "Baseline arms without resources do not match instructional dose.",
            "Warmup and item selection are concept-level approximations.",
            "Absolute action-indexed exogenous shocks may be misaligned across differing resource counts.",
        ],
    }


def markdown(summary: dict) -> str:
    lines = [
        "# IJCAI 2027 — Step 101 independently recomputed Step 100 summary",
        "",
        "**SYNTHETIC DEVELOPMENT ONLY. NOT EVIDENCE OF HUMAN LEARNING.**",
        "",
        f"Audit: {summary['status']}; {summary['verified_episode_count']} fictional episodes.",
        "",
        f"**Claim gate:** {summary['screening_outcome']}",
        "",
        "| Scenario | Step 99 − V3 posttest accuracy | Descriptive interval | W/T/L |",
        "|---|---:|---:|---:|",
    ]
    for scenario, r in summary["primary_scenario_results"].items():
        ci = r["descriptive_interval"]
        w, t, l = r["wins_ties_losses"]
        lines.append(
            f"| {scenario} | {r['mean_difference']:+.6f} | "
            f"[{ci[0]:+.6f}, {ci[1]:+.6f}] | {w}/{t}/{l} |"
        )
    lines += [
        "", "## Policy-dose differences",
        "| Scenario | Policy | Mean resources | Mean nominal cost | Mean posttest accuracy |",
        "|---|---|---:|---:|---:|",
    ]
    for scenario, by_policy in summary["resource_dose_and_cost_diagnostics"].items():
        for policy, d in by_policy.items():
            lines.append(
                f"| {scenario} | {policy} | {d['mean_recovery_resources']:.3f} | "
                f"{d['mean_nominal_cost']:.5f} | {d['mean_posttest_accuracy']:.5f} |"
            )
    lines += [
        "", "## Mandatory qualifications",
        *[f"- {item}" for item in summary["limitations"]],
        "- V3 and Step 99 superiority, risk robustness, and learner recovery are not established.",
        "- No live enrollment without independent educational, legal, privacy and institutional approvals.",
        "- This audit does not create a pristine heldout cohort or certify a novel IJCAI algorithm.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.input, args.output, args.markdown)}) != 3:
        raise ValueError("Input, output and Markdown files must be distinct")
    if args.output.exists() or args.markdown.exists():
        raise FileExistsError("Prior audit artifacts must not be overwritten")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = verify(source)
    result["input_json_sha256"] = sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    args.markdown.write_text(markdown(result), encoding="utf-8")
    print(f"Validated {result['verified_episode_count']} development-only episodes.")
    print("Claim gate:", result["screening_outcome"])
    print("Saved audit:", args.output)
    print("Saved supervisor summary:", args.markdown)


if __name__ == "__main__":
    main()
