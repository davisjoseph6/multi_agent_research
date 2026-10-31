"""Step 98: exact inventory-aware *single-decision* research certificate.

No policy substitution, human data, rollout claims, or RCT changes.

This mirrors one important V3 root constraint: resource targets must also
have at least one unused practice question. Unlike the V3 internal rollout,
the snapshot explicitly records finite practice inventory. It is NOT an
execution-equivalent multi-step model of V3.

Rates are hypotheses / explicit lower and upper bounds, NOT calibrated.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import csv
from pathlib import Path
from typing import Mapping

from .study_v3_pomcp import ACTIONS, CONCEPTS, PRACTICE, RECOVERY_ACTIONS, GenerativeAssumptions
from .step97_policy_drift_certificate import N, checked_distribution, probability


@dataclass(frozen=True)
class PracticeInventory:
    """Current unused practice questions and resource slots in a session.

    Exactly 55 practice questions are in the draft bank initially, distributed
    seven per concept except six for Nudge Theory. After any practice answer,
    decrement exactly one of these counts. The class does not track the order
    of the 20/20/15 session boundaries or the between-session reset of two
    resource slots. The caller must supply an authentic state.
    """
    remaining: tuple[int, ...]
    resources_left: int
    resource_actions: tuple[str, ...] = RECOVERY_ACTIONS
    forced_warmup: bool = False

    def __post_init__(self) -> None:
        if len(self.remaining) != N or any(type(x) is not int or x < 0 for x in self.remaining):
            raise ValueError("Exactly eight nonnegative practice counts required")
        if type(self.resources_left) is not int or not 0 <= self.resources_left <= 2:
            raise ValueError("Expected current-session resource slots in [0,2]")
        if (not isinstance(self.resource_actions, tuple)
                or len(set(self.resource_actions)) != len(self.resource_actions)
                or any(x not in RECOVERY_ACTIONS for x in self.resource_actions)):
            raise ValueError("Invalid resource action types")
        if type(self.forced_warmup) is not bool:
            raise ValueError("Invalid warmup indicator")

    def legal_actions(self) -> tuple[tuple[str, str], ...]:
        active = tuple(c for c, count in zip(CONCEPTS, self.remaining) if count > 0)
        practice = tuple((PRACTICE, c) for c in active)
        if not self.resources_left or self.forced_warmup:
            return practice
        return practice + tuple((kind, c) for c in active for kind in self.resource_actions)

    def active_concepts(self) -> tuple[str, ...]:
        return tuple(c for c, n in zip(CONCEPTS, self.remaining) if n > 0)


def read_draft_practice_inventory(path: str | Path) -> tuple[tuple[int, ...], str]:
    """Read original draft bank; never infer expert acceptance from this file."""
    path = Path(path)
    from hashlib import sha256

    with path.open(encoding="utf-8-sig", newline="") as inp:
        reader = csv.DictReader(inp)
        if not reader.fieldnames or not {"item_id", "form", "concept"} <= set(reader.fieldnames):
            raise ValueError("Missing item bank headers")
        items = list(reader)
    if len(items) != 95:
        raise ValueError("Expected the exact 95-row RCT candidate draft bank")
    ids = [row["item_id"] for row in items]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("Missing or repeated item ID")
    forms = Counter(row["form"] for row in items)
    if forms != {"pretest": 16, "posttest": 16, "practice": 55, "recovery_drop2": 8}:
        raise ValueError("Unexpected RCT candidate item forms")
    if any(row["concept"] not in CONCEPTS for row in items):
        raise ValueError("Unknown concept")
    counts = Counter(row["concept"] for row in items if row["form"] == "practice")
    if any(counts[c] <= 0 for c in CONCEPTS):
        raise ValueError("At least one concept has no practice items")
    return tuple(counts[c] for c in CONCEPTS), sha256(path.read_bytes()).hexdigest()


def feasible_coverage_mixture(
    inventory: PracticeInventory,
    *, primary: tuple[str, str], exploration: object,
) -> dict[tuple[str, str], Fraction]:
    """Choose primary action or uniformly explore currently feasible practice.

    This is a proposed hypothetical distribution, NOT a deployed V3 policy.
    All practice concepts absent from the current inventory have zero support.
    """
    legal = inventory.legal_actions()
    if not legal or primary not in legal:
        raise ValueError("Primary action is not feasible in this snapshot")
    eps = probability(exploration)
    active = inventory.active_concepts()
    weights: dict[tuple[str, str], Fraction] = {primary: Fraction(1) - eps}
    for concept in active:
        action = (PRACTICE, concept)
        weights[action] = weights.get(action, Fraction(0)) + eps / len(active)
    return checked_distribution(weights)


def robust_statewise_certificate(
    inventory: PracticeInventory,
    action_distribution: Mapping[tuple[str, str], object],
    *,
    learning_lower: Mapping[str, object],
    forgetting_upper: Mapping[str, object],
) -> dict:
    """Exact worst-state *one-step* drift under a rectangular rate uncertainty set.

    Lower learning bounds are per action type, and upper forgetting bounds
    are per mastered concept. Assuming every target unmastered concept learns
    with a rate at least its specified lower bound, and every mastered
    concept forgets with a rate at most the specified upper bound, the
    worst expected D change across all non-target latent states and the
    stated uncertainty box is:
      (sum_j f_j^+ - min_k(f_k^+ + sum_a q_(a,k)*p_a^-)) / N.

    No claim is made about independent human learner interventions,
    unknown true rates, later inventory depletion or controller adaptation.
    """
    legal = set(inventory.legal_actions())
    if not legal:
        raise ValueError("No practice-stage actions left; no drift assertion possible")
    weights = checked_distribution(action_distribution)
    if any(action not in legal for action in weights):
        raise ValueError("Distribution includes an unavailable action")
    if set(learning_lower) != set(ACTIONS) or set(forgetting_upper) != set(CONCEPTS):
        raise ValueError("Complete learning and forgetting uncertainty bounds required")
    lower = {action: probability(learning_lower[action]) for action in ACTIONS}
    upper = {concept: probability(forgetting_upper[concept]) for concept in CONCEPTS}
    effective = tuple(
        sum((weight * lower[action]
             for (action, target), weight in weights.items() if target == concept),
            Fraction(0))
        for concept in CONCEPTS
    )
    forget = tuple(upper[concept] for concept in CONCEPTS)
    worst_index = min(range(N), key=lambda i: effective[i] + forget[i])
    worst_drift = (sum(forget, Fraction(0)) -
                   effective[worst_index] - forget[worst_index]) / N
    strict = worst_drift < 0
    return {
        "scope": "SINGLE_DECISION_FINITE_INVENTORY_RECTANGULAR_RATE_MODEL",
        "not_a_v3_or_rct_policy_guarantee": True,
        "not_real_student_evidence": True,
        "all_question_counts": {c: inventory.remaining[i] for i, c in enumerate(CONCEPTS)},
        "session_resource_slots": inventory.resources_left,
        "forced_warmup": inventory.forced_warmup,
        "available_action_count": len(legal),
        "actions_with_positive_weight": sum(w > 0 for w in weights.values()),
        "infeasible_target_concepts": list(set(CONCEPTS) - set(inventory.active_concepts())),
        "worst_latent_unmastered_concept": CONCEPTS[worst_index],
        "worst_expected_deficit_change": str(worst_drift),
        "strict_uniform_negative_one_step_drift": strict,
        "uniform_drift_margin": str(-worst_drift if strict else Fraction(0)),
        "effective_learning_lower_bounds": {c: str(effective[i]) for i, c in enumerate(CONCEPTS)},
        "forgetting_upper_bounds": {c: str(forget[i]) for i, c in enumerate(CONCEPTS)},
        "assumptions": "Single target per action; per-concept action-independent forgetting; bounds valid at supplied history; all weighted actions feasible",
    }


def hypothetical_rate_bounds() -> tuple[dict[str, Fraction], dict[str, Fraction]]:
    model = GenerativeAssumptions()
    return ({a: probability(model.rate(a)) for a in ACTIONS},
            {c: Fraction(0) for c in CONCEPTS})


def never_learned_floor(
    *, practice_opportunities: int, resource_opportunities: int,
    practice_success_upper: object, resource_success_upper: object,
) -> Fraction:
    """Lower bound on failure of one initially unmastered concept.

    Under the assumption that each conditional opportunity has probability
    of learning at most the supplied upper bound, irrespective of history,
    and at most the specified number of each opportunity can be offered:
      P(never learned) >= (1-p_practice)^n * (1-p_resource)^R.
    This is NOT an empirical estimate or a bound on all concepts mastering.
    """
    if (type(practice_opportunities) is not int or practice_opportunities < 0
            or type(resource_opportunities) is not int or resource_opportunities < 0):
        raise ValueError("Nonnegative integer opportunity counts required")
    a = probability(practice_success_upper)
    b = probability(resource_success_upper)
    return (1 - a) ** practice_opportunities * (1 - b) ** resource_opportunities


def demo_bank_snapshots(path: str | Path) -> dict:
    counts, digest = read_draft_practice_inventory(path)
    p, f = hypothetical_rate_bounds()

    def evaluate(inv: PracticeInventory) -> dict:
        legal = inv.legal_actions()
        if not legal:
            return {"status": "NO_PRACTICE_ACTION_REMAINS",
                    "remaining_practice_items": sum(inv.remaining),
                    "strict_uniform_drift_certificate": False}
        weights = feasible_coverage_mixture(inv, primary=legal[0], exploration=1)
        result = robust_statewise_certificate(inv, weights,
                                              learning_lower=p, forgetting_upper=f)
        result["status"] = "CERTIFIED_FOR_SUPPLIED_SNAPSHOT_ONLY" if result[
            "strict_uniform_negative_one_step_drift"] else "NO_UNIFORM_CERTIFICATE"
        return result

    exhausted_last = tuple(0 if c == "Nudge Theory" else counts[i]
                           for i, c in enumerate(CONCEPTS))
    return {
        "synthetic_only": True,
        "rct_candidate_draft_content_reviewed": False,
        "source_csv_sha256": digest,
        "original_bank_counts": dict(zip(CONCEPTS, counts)),
        "initial_inventory": evaluate(PracticeInventory(counts, resources_left=2)),
        "nudge_practice_exhausted": evaluate(PracticeInventory(exhausted_last, resources_left=2)),
        "all_practice_exhausted": evaluate(PracticeInventory((0,) * N, resources_left=0)),
        "hypothetical_nudge_nonmastery_floor_with_six_practice_and_six_resources":
            str(never_learned_floor(practice_opportunities=6, resource_opportunities=6,
                                    practice_success_upper=p[PRACTICE],
                                    resource_success_upper="0.14")),
        "warning": "Not a longitudinal protocol model, human learning result, or release authorization",
    }
