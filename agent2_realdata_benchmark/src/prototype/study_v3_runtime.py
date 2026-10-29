"""Opt-in EIGHT-CONCEPT POMCP synthetic runtime; v2 default unaffected.

Do not use for real enrollment, learning claims, or an approved RCT.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from .study_v2 import Belief, CONCEPTS, GreedyPolicy, RECOVERY_ACTIONS
from .study_v2_runtime import ProtocolError, SyntheticProtocolEngine
from .study_v3_pomcp import EightConceptPOMCP, PRACTICE


class SyntheticPOMCPProtocolEngine(SyntheticProtocolEngine):
    """Uses planner for A, the unchanged greedy B and fixed C.

    Every offered synthetic resource consumes one of max_resources_per_session;
    unlike the historical rule-based implementation, a resource is one action,
    not an entire four-stage episode. This is a DIFFERENT experimental policy.
    """

    def __init__(self, path, bank, *, planner: EightConceptPOMCP | None = None,
                 max_resources_per_session: int = 2):
        if type(max_resources_per_session) is not int or not 0 <= max_resources_per_session <= 10:
            raise ValueError("invalid POMCP resource budget")
        self.planner = planner or EightConceptPOMCP()
        self.max_resources_per_session = max_resources_per_session
        super().__init__(path, bank)
        config = dict(
            protocol="synthetic_pomcp_v3_2026-10-29",
            model_hash=self.planner.assumptions.fingerprint,
            planner_horizon=self.planner.horizon,
            planner_simulations=self.planner.simulations,
            planner_exploration=self.planner.exploration,
            planner_discount=self.planner.discount,
            max_resources_per_session=self.max_resources_per_session,
            item_bank_hash=self.bank_hash,
            fixed_schedule="balanced_round_robin_v3",
            pretest_bkt="posterior_only_v3",
        )
        serialized = json.dumps(config, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS synthetic_v3_config ("
                       "id INTEGER PRIMARY KEY CHECK (id=1), json TEXT NOT NULL)")
            prior = db.execute("SELECT json FROM synthetic_v3_config WHERE id=1").fetchone()
            if prior is None:
                present = db.execute("SELECT COUNT(*) FROM synthetic_participants").fetchone()[0]
                if present:
                    raise ProtocolError("cannot upgrade an existing v2 dataset into v3")
                db.execute("INSERT INTO synthetic_v3_config(id,json) VALUES(1,?)",
                           (serialized,))
            elif prior[0] != serialized:
                raise ProtocolError("synthetic v3 protocol configuration changed")

    def _candidate(self, s):
        # Versioned balanced nonadaptive schedule for arm C. The original
        # v2 FixedPolicy sorts all item IDs, which can omit entire concepts
        # in a 55-of-64-item experiment. This schedule interleaves all eight.
        if s["arm"] == "C" and s["stage"] == "practice":
            candidates = [q for q in self.bank.values() if q.form == "practice"]
            per_concept = {c: sorted((q for q in candidates if q.concept == c),
                                     key=lambda q: (q.difficulty,q.item_id))
                           for c in CONCEPTS}
            schedule = [q for offset in range(max(len(q) for q in per_concept.values()))
                        for c in CONCEPTS for q in per_concept[c][offset:offset+1]]
            item = next((q for q in schedule if q.item_id not in s["used"]), None)
            if item is None:
                raise ValueError("no unused fixed-schedule item")
            return dict(action=PRACTICE, concept=item.concept, item_id=item.item_id,
                        selector="v3_balanced_fixed_schedule", synthetic_only=True)
        if s["arm"] != "A" or s["stage"] != "practice":
            return super()._candidate(s)
        candidates = [q for q in self.bank.values()
                      if q.form == "practice" and q.item_id not in s["used"]]
        if not candidates:
            raise ValueError("no unused practice items")
        belief = Belief(s["mastery"].copy())
        # Avoid inferring a DEGRADATION EVENT from low starting mastery.
        # The first action each session is always an ordinary practice item.
        if s["index"] == 0:
            d = GreedyPolicy().choose(belief, candidates)
            return dict(action=PRACTICE, concept=d.concept, item_id=d.item_id,
                        selector="pomcp_warmup_greedy", synthetic_only=True)
        spent = s["recovery"].get("pomcp_resource_spent", 0)
        remaining = max(0, self.max_resources_per_session - spent)
        concepts = [c for c in belief.mastery if any(q.concept == c for q in candidates)]
        stable_seed = int.from_bytes(sha256(json.dumps({
            "mastery": s["mastery"], "used": s["used"],
            "session": s["session"], "index": s["index"],
            "spent": spent, "model": self.planner.assumptions.fingerprint,
        },sort_keys=True).encode()).digest()[:8], "big")
        result = self.planner.choose(
            belief.mastery, practice_concepts=concepts,
            resource_actions=RECOVERY_ACTIONS if remaining else (),
            resources_left=remaining, seed=stable_seed)
        if result.action == PRACTICE:
            selected = min((q for q in candidates if q.concept == result.concept),
                           key=lambda q: (q.difficulty, q.item_id))
            item_id = selected.item_id
        else:
            if remaining == 0:
                raise AssertionError("planner selected unavailable resource")
            s["recovery"]["pomcp_resource_spent"] = spent + 1
            item_id = None
            if result.action == "DROP_2":
                choices = sorted((q for q in self.bank.values()
                                  if q.form == "recovery_drop2" and q.concept == result.concept),
                                 key=lambda q:q.item_id)
                if not choices:
                    raise ValueError("missing DROP_2 item")
                item_id = choices[0].item_id
        return dict(action=result.action, concept=result.concept, item_id=item_id,
                    selector="pomcp_eight_concept_synthetic",
                    planning_trace=asdict(result))
