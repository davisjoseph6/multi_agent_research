"""Aggregate-only *fictional* randomized feasibility reporting draft.

The supervisor PROPOSED a 3-arm feasibility pilot of 90 initially enrolled
students pending statistician review. This module explicitly does NOT perform
human registration, consent, arm assignment, outcome inference, database IO
or release authorization. It accepts only aggregates marked fictional_only.

Wilson intervals describe count uncertainty, not causal treatment effects.
Candidate progression thresholds are omitted until the PI/statistician freeze
their denominators, rules and interpretation.
"""
from __future__ import annotations

from math import sqrt

ARMS = ("A", "B", "C")
ARM_KEYS = (
    "randomized", "visit1_attended", "visit2_attended", "visit3_attended",
    "protocol_completed", "posttest_observed", "mvas_observed",
    "mvas_expected", "adjacent_visit_pairs_on_time",
    "application_requests", "application_failures",
    "intervention_fidelity_deviations", "critical_incidents_reported",
)
SCREEN_KEYS = ("approached", "screened", "eligible", "consented")
SCHEMA = "IJCAI2027_SYNTHETIC_FEASIBILITY_COUNTS_V1"


def _is_nonnegative_int(value):
    return type(value) is int and value >= 0


def wilson_95(k: int, n: int) -> dict:
    """Descriptive Wilson 95% interval (z=1.95996398454); null when n=0."""
    if not _is_nonnegative_int(n) or not _is_nonnegative_int(k) or k > n:
        raise ValueError("valid integer numerator <= denominator required")
    if n == 0:
        return {"numerator": k, "denominator": n, "rate": None,
                "lower_95": None, "upper_95": None}
    z = 1.959963984540054
    p = k / n
    z2 = z * z
    center = (p + z2 / (2 * n)) / (1 + z2 / n)
    margin = z / (1 + z2 / n) * sqrt(p * (1-p) / n + z2 / (4*n*n))
    return {
        "numerator": k, "denominator": n,
        "rate": round(p, 6),
        "lower_95": round(max(0, center-margin), 6),
        "upper_95": round(min(1, center+margin), 6),
    }


def _validate(payload: dict) -> None:
    if type(payload) is not dict or set(payload) != {
        "schema_version", "fictional_only", "screening", "arms",
    }:
        raise ValueError("expected exact aggregate-only synthetic schema")
    if payload["schema_version"] != SCHEMA or payload["fictional_only"] is not True:
        raise ValueError("only explicitly fictional aggregate inputs allowed")
    screening = payload["screening"]
    if type(screening) is not dict or set(screening) != set(SCREEN_KEYS) or \
            any(not _is_nonnegative_int(v) for v in screening.values()):
        raise ValueError("screening must contain four nonnegative integers")
    if not (screening["approached"] >= screening["screened"]
            >= screening["eligible"] >= screening["consented"]):
        raise ValueError("screening flow must be monotonic")
    arms = payload["arms"]
    if type(arms) is not dict or set(arms) != set(ARMS):
        raise ValueError("exactly three arm-level aggregate objects required")
    for name in ARMS:
        row = arms[name]
        if type(row) is not dict or set(row) != set(ARM_KEYS) or \
                any(not _is_nonnegative_int(v) for v in row.values()):
            raise ValueError(f"{name}: arm metrics must be exact nonnegative integers")
        if not (row["randomized"] >= row["visit1_attended"]
                >= row["visit2_attended"] >= row["visit3_attended"]
                >= row["protocol_completed"]):
            raise ValueError(f"{name}: visit attrition counts inconsistent")
        if (row["posttest_observed"] > row["visit3_attended"] or
                row["protocol_completed"] > row["posttest_observed"]):
            raise ValueError(f"{name}: observed posttest counts inconsistent")
        expected_mvas = 2 * (
            row["visit1_attended"] + row["visit2_attended"] +
            row["visit3_attended"]
        )
        if (row["mvas_expected"] != expected_mvas
                or row["mvas_observed"] > expected_mvas):
            raise ValueError(f"{name}: impossible M-VAS opportunity counts")
        if row["adjacent_visit_pairs_on_time"] > (
                row["visit2_attended"] + row["visit3_attended"]):
            raise ValueError(f"{name}: too many on-time adjacent visit pairs")
        if row["application_failures"] > row["application_requests"]:
            raise ValueError(f"{name}: failed requests exceed attempts")
    if sum(arms[a]["randomized"] for a in ARMS) > screening["consented"]:
        raise ValueError("more randomized than consenting fictional participants")


def summarize_synthetic_feasibility(payload: dict) -> dict:
    """Pure computation with no human identifiers or real-world release paths."""
    _validate(payload)
    rows = payload["arms"]
    screen = payload["screening"]
    total = {
        name: sum(rows[a][name] for a in ARMS) for name in ARM_KEYS
    }

    def outcomes(group):
        return {
            "protocol_completion_among_randomized": wilson_95(
                group["protocol_completed"], group["randomized"]
            ),
            "visit3_attendance_among_randomized": wilson_95(
                group["visit3_attended"], group["randomized"]
            ),
            "posttest_capture_among_visit3_attendees": wilson_95(
                group["posttest_observed"], group["visit3_attended"]
            ),
            "mvas_capture_among_attended_visit_opportunities": wilson_95(
                group["mvas_observed"], group["mvas_expected"]
            ),
            "adjacent_visit_pairs_on_time": wilson_95(
                group["adjacent_visit_pairs_on_time"],
                group["visit2_attended"] + group["visit3_attended"],
            ),
            "application_failure_rate": wilson_95(
                group["application_failures"], group["application_requests"]
            ),
            "intervention_fidelity_deviations_reported":
                group["intervention_fidelity_deviations"],
            "critical_incidents_reported": group["critical_incidents_reported"],
            "raw_aggregate_counts": dict(group),
        }

    return {
        "kind": "FICTIONAL_THREE_ARM_FEASIBILITY_REPORT_DRAFT",
        "schema_version": SCHEMA,
        "result": "DESCRIPTIVE_SYNTHETIC_ONLY",
        "fictional_only": True,
        "primary_objectives": (
            "recruitment", "retention", "three_visit_protocol_adherence",
            "intervention_fidelity", "software_reliability",
            "data_completeness",
        ),
        "screening_counts": dict(screen),
        "recruitment_screened_per_approached": wilson_95(
            screen["screened"], screen["approached"]
        ),
        "eligible_per_screened": wilson_95(
            screen["eligible"], screen["screened"]
        ),
        "randomized_per_consented": wilson_95(
            total["randomized"], screen["consented"]
        ),
        "overall": outcomes(total),
        "arms": {arm: outcomes(rows[arm]) for arm in ARMS},
        "proposed_initial_enrollment": 90,
        "proposed_n_not_statistically_approved": True,
        "progression_criteria_signed_and_frozen": False,
        "formal_efficacy_or_fatigue_noninferiority_analysis": False,
        "fatigue_instrument_wording_and_validity_approved": False,
        "ethics_and_data_protection_approved": False,
        "human_enrollment_authorized": False,
        "independent_final_release_qa_performed": False,
        "calculation_limits": (
            "Inputs are fictional aggregates only, not human data; "
            "Wilson intervals are descriptive. Visit-pair percentages count "
            "eligible pairs among visits 2 and 3. Completing the full protocol "
            "requires visit 3 and observed posttest. Missingness and withdrawal "
            "denominators need PI/statistician confirmation before live study. "
            "No treatment efficacy or noninferiority inference is performed."
        ),
    }
