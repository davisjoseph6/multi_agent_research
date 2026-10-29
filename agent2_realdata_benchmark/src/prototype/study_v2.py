"""Provisional three-arm study prototype (synthetic data ONLY).

No live enrolment, ethics approval, participant identity, or causal efficacy claim.
The original Step-71 study specification is intentionally not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import math
import random
import sqlite3
from typing import Literal

CONCEPTS = (
    "Utility", "Loss Aversion", "Anchoring", "Sunk Cost", "Framing",
    "Heuristics", "Prospect Theory", "Nudge Theory",
)
BLOOM = ("remember", "understand", "apply", "analyze", "evaluate", "create")
ARMS = ("A", "B", "C")
SESSION_TARGETS = (20, 20, 15)
RECOVERY_ACTIONS = ("CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT")
FORMS = ("pretest", "practice", "posttest", "recovery_drop2")
SCHEMA_VERSION = "ijcai2027-provisional-v2"


@dataclass(frozen=True)
class Item:
    item_id: str
    form: str
    concept: str
    bloom: str
    prompt: str
    options: tuple[tuple[str, str], ...]
    answer_id: str
    difficulty: float = 0.5
    status: str = "draft"

    def __post_init__(self):
        if self.form not in FORMS or self.concept not in CONCEPTS or self.bloom not in BLOOM:
            raise ValueError("invalid form, concept, or Bloom classification")
        if not self.item_id or not self.prompt.strip() or not 0 <= self.difficulty <= 1:
            raise ValueError("invalid item ID, prompt, or difficulty")
        if self.status not in ("draft", "expert_reviewed"):
            raise ValueError("invalid author review status")
        ids = [option[0] for option in self.options]
        if len(ids) != len(set(ids)) or self.answer_id not in ids:
            raise ValueError("duplicate option IDs or invalid answer")
        if any(not x or not y.strip() for x, y in self.options):
            raise ValueError("empty option text or ID")
        if self.form == "recovery_drop2":
            if len(ids) != 2:
                raise ValueError("DROP_2 must have two options")
        elif not 2 <= len(ids) <= 6:
            raise ValueError("regular question must have 2-6 options")

    def public(self) -> dict:
        """Never send the answer key to a student browser."""
        return {key: getattr(self, key) for key in
                ("item_id", "form", "concept", "bloom", "prompt", "options")}


def validate_bank(items: list[Item], *, full: bool = False) -> dict:
    if not all(isinstance(x, Item) for x in items):
        raise ValueError("all question-bank records must be Item objects")
    ids = [x.item_id for x in items]
    prompts = [" ".join(x.prompt.casefold().split()) for x in items]
    if len(ids) != len(set(ids)) or len(prompts) != len(set(prompts)):
        raise ValueError("duplicate question ID or wording")
    counts = dict(Counter(x.form for x in items))
    if full:
        if counts.get("pretest") != 16 or counts.get("posttest") != 16:
            raise ValueError("exactly 16 pretest and 16 posttest questions required")
        if counts.get("practice", 0) < sum(SESSION_TARGETS):
            raise ValueError("insufficient distinct practice questions")
        if {x.concept for x in items if x.form == "practice"} != set(CONCEPTS):
            raise ValueError("practice bank does not cover all concepts")
        if counts.get("recovery_drop2", 0) < len(CONCEPTS):
            raise ValueError("need at least one two-option recovery item per concept")
        for concept in CONCEPTS:
            if sum(x.form == "pretest" and x.concept == concept for x in items) < 1:
                raise ValueError("pretest missing concept")
            if sum(x.form == "posttest" and x.concept == concept for x in items) < 1:
                raise ValueError("posttest missing concept")
    return counts


def require_expert_reviewed(items: list[Item]) -> None:
    """Mechanical release gate; cannot substitute for actual external review."""
    validate_bank(items, full=True)
    if not all(item.status == "expert_reviewed" for item in items):
        raise ValueError("item bank includes unreviewed content")


def synthetic_bank() -> list[Item]:
    """Fixtures are NOT scientifically valid items; never use them on learners."""
    items = []
    for c, concept in enumerate(CONCEPTS):
        for form, number in (("pretest", 2), ("posttest", 2), ("practice", 8),
                             ("recovery_drop2", 1)):
            for i in range(number):
                item_id = f"SYN_{form}_{c:02}_{i:02}"
                choices = (("A", "Synthetic option A"), ("B", "Synthetic option B"))
                if form != "recovery_drop2":
                    choices += (("C", "Synthetic option C"),)
                items.append(Item(
                    item_id, form, concept, BLOOM[i % len(BLOOM)],
                    f"SYNTHETIC ONLY: {concept} {form} fixture {i}.",
                    choices, "B", difficulty=0.25 + 0.08 * (i % 6),
                ))
    validate_bank(items, full=True)
    return items


@dataclass(frozen=True)
class BKT:
    learn: float = 0.10
    slip: float = 0.10
    guess: float = 0.25

    def __post_init__(self):
        if any(not 0 <= v <= 1 for v in (self.learn, self.slip, self.guess)):
            raise ValueError("BKT parameters must lie in [0,1]")

    def posterior(self, prior: float, correct: bool) -> float:
        if not 0 <= prior <= 1:
            raise ValueError("mastery probability outside [0,1]")
        likelihood_master = (1 - self.slip) if correct else self.slip
        likelihood_novice = self.guess if correct else (1 - self.guess)
        numerator = prior * likelihood_master
        denominator = numerator + (1 - prior) * likelihood_novice
        if denominator == 0:
            raise ValueError("impossible observation under chosen BKT model")
        return numerator / denominator

    def update(self, prior: float, correct: bool) -> float:
        posterior = self.posterior(prior, correct)
        return posterior + (1 - posterior) * self.learn


@dataclass
class Belief:
    mastery: dict[str, float] = field(default_factory=lambda: {c: 0.20 for c in CONCEPTS})
    params: BKT = field(default_factory=BKT)

    def __post_init__(self):
        if set(self.mastery) != set(CONCEPTS):
            raise ValueError("mastery state must cover exactly eight concepts")
        if any(not 0 <= x <= 1 for x in self.mastery.values()):
            raise ValueError("invalid mastery probability")

    @property
    def degradation(self) -> float:
        return 1 - sum(self.mastery.values()) / len(CONCEPTS)

    def observe(self, concept: str, correct: bool) -> None:
        if concept not in self.mastery:
            raise ValueError("unknown concept")
        self.mastery[concept] = self.params.update(self.mastery[concept], correct)


@dataclass(frozen=True)
class Decision:
    action: str
    concept: str
    item_id: str | None = None
    reason: str = ""


class FixedPolicy:
    arm = "C"

    def choose(self, belief: Belief, candidates: list[Item]) -> Decision:
        if not candidates:
            raise ValueError("no unused practice items")
        item = sorted(candidates, key=lambda x: x.item_id)[0]
        return Decision("QUESTION", item.concept, item.item_id, "fixed ID order")


class GreedyPolicy:
    arm = "B"

    def choose(self, belief: Belief, candidates: list[Item]) -> Decision:
        if not candidates:
            raise ValueError("no unused practice items")
        item = min(candidates, key=lambda x: (
            belief.mastery[x.concept], x.difficulty, x.item_id,
        ))
        return Decision("QUESTION", item.concept, item.item_id, "minimum estimated mastery")


@dataclass
class RecoveryStatus:
    attempts: int = 0   # A complete recovery episode counts as one attempt.
    stage: int = 0      # 0=no active episode; 1..4=current stage index + 1
    concept: str | None = None
    nonrecoverable: bool = False


class RuleBasedSelfHealing:
    arm = "A"

    def __init__(self, threshold: float = 0.5, max_attempts: int = 2):
        if not 0 <= threshold <= 1 or max_attempts < 0:
            raise ValueError("invalid recovery threshold or limit")
        self.threshold = threshold
        self.max_attempts = max_attempts
        self.greedy = GreedyPolicy()

    def choose(self, belief: Belief, candidates: list[Item],
               completed_responses: int, status: RecoveryStatus) -> Decision:
        if status.stage:
            action = RECOVERY_ACTIONS[status.stage - 1]
            status.stage += 1
            if status.stage > len(RECOVERY_ACTIONS):
                status.stage = 0
                status.attempts += 1
            return Decision(action, status.concept or CONCEPTS[0], reason="recovery episode")
        if completed_responses and belief.degradation > self.threshold:
            if status.attempts < self.max_attempts:
                status.concept = min(belief.mastery, key=belief.mastery.get)
                status.stage = 2
                return Decision(RECOVERY_ACTIONS[0], status.concept,
                                reason="degradation above threshold")
            status.nonrecoverable = True
        return self.greedy.choose(belief, candidates)


class OneConceptPOMCP:
    """A small, actual history-tree Monte Carlo planner for one concept.

    SYNTHETIC generative model: not calibrated to actual learners. Root state
    is sampled from BKT belief. Simulations use history (action, observation)
    tree nodes and UCB1 with random rollouts. Intended for benchmark research,
    not a clinical/educational treatment decision.
    """

    ACTIONS = ("PRACTICE", "CONCEPT_SUMMARY", "WORKED_EXAMPLE")

    def __init__(self, horizon: int = 4, simulations: int = 150,
                 exploration: float = 1.0, discount: float = 0.95,
                 seed: int = 42):
        if horizon < 1 or simulations < 1 or exploration < 0 or not 0 < discount <= 1:
            raise ValueError("invalid POMCP planning parameters")
        self.horizon = horizon
        self.simulations = simulations
        self.exploration = exploration
        self.discount = discount
        self.seed = seed

    @staticmethod
    def model_step(mastered: bool, action: str, rng: random.Random):
        # ASSUMED synthetic transitions, not observed empirical effects.
        learning = {"PRACTICE": .06, "CONCEPT_SUMMARY": .12,
                    "WORKED_EXAMPLE": .18}[action]
        cost = {"PRACTICE": .01, "CONCEPT_SUMMARY": .05,
                "WORKED_EXAMPLE": .09}[action]
        became_mastered = mastered or rng.random() < learning
        correct = rng.random() < (.90 if became_mastered else .25)
        reward = (1.0 if became_mastered and not mastered else 0.0) - cost
        return became_mastered, int(correct), reward

    def choose(self, prior_mastery: float, *, seed: int | None = None) -> str:
        if not 0 <= prior_mastery <= 1:
            raise ValueError("invalid BKT mastery belief")
        rng = random.Random(self.seed if seed is None else seed)
        visits = Counter()
        edge_visits = Counter()
        edge_returns = Counter()

        def rollout(state, depth):
            if depth == 0:
                return 0.0
            action = rng.choice(self.ACTIONS)
            new_state, _obs, reward = self.model_step(state, action, rng)
            return reward + self.discount * rollout(new_state, depth - 1)

        def simulate(state, history, depth):
            if depth == 0:
                return 0.0
            if visits[history] == 0:
                visits[history] += 1
                return rollout(state, depth)
            untried = [a for a in self.ACTIONS if edge_visits[(history, a)] == 0]
            if untried:
                action = rng.choice(untried)
            else:
                action = max(self.ACTIONS, key=lambda a:
                             edge_returns[(history, a)] / edge_visits[(history, a)]
                             + self.exploration * math.sqrt(
                                 math.log(visits[history] + 1) / edge_visits[(history, a)]))
            new_state, obs, reward = self.model_step(state, action, rng)
            future = simulate(new_state, history + ((action, obs),), depth - 1)
            value = reward + self.discount * future
            visits[history] += 1
            edge_visits[(history, action)] += 1
            edge_returns[(history, action)] += value
            return value

        for _ in range(self.simulations):
            root = rng.random() < prior_mastery
            simulate(root, (), self.horizon)
        return max(self.ACTIONS, key=lambda a: (
            edge_visits[((), a)] > 0,
            edge_returns[((), a)] / edge_visits[((), a)]
            if edge_visits[((), a)] else float("-inf"),
            -self.ACTIONS.index(a),
        ))


@dataclass
class SimulatedLearner:
    """Synthetic latent state. Do not interpret as real learner behavior."""
    latent: dict[str, float]
    belief: Belief = field(default_factory=Belief)

    def assess(self, item: Item, rng: random.Random, *, baseline: bool = False) -> bool:
        """Assessment responses never cause synthetic learning transitions."""
        knowledge = self.latent[item.concept]
        correct = rng.random() < knowledge * .90 + (1 - knowledge) * .25
        if baseline:
            self.belief.observe(item.concept, correct)
        return correct

    def answer(self, item: Item, rng: random.Random) -> bool:
        correct = self.assess(item, rng, baseline=True)
        # Hypothetical learning rate, supplied only for synthetic software tests.
        knowledge = self.latent[item.concept]
        self.latent[item.concept] += (1 - knowledge) * .03
        return correct

    def resource(self, concept: str, action: str) -> None:
        if action not in RECOVERY_ACTIONS:
            raise ValueError("invalid resource action")
        # Hypothetical synthetic effect; not a factual educational outcome.
        if action != "DROP_2":
            k = self.latent[concept]
            self.latent[concept] = k + (1 - k) * .02


def allocate_arms(n: int, rng: random.Random) -> list[str]:
    if n < 0 or n % 3:
        raise ValueError("synthetic allocation requires multiple of three")
    arms = []
    for _ in range(n // 3):
        block = list(ARMS)
        rng.shuffle(block)
        arms.extend(block)
    return arms


def mock_study(n: int = 9, seed: int = 71) -> dict:
    """Complete three-session SCRIPTED MOCK; zero real-world causal evidence."""
    rng = random.Random(seed)
    bank = synthetic_bank()
    by_form = {form: [q for q in bank if q.form == form] for form in FORMS}
    allocations = allocate_arms(n, rng)
    participants = []
    for p, arm in enumerate(allocations):
        learner = SimulatedLearner({c: .2 + .1 * rng.random() for c in CONCEPTS})
        seen = set()
        pre = [int(learner.assess(q, rng, baseline=True)) for q in by_form["pretest"]]
        sessions = []
        for session_idx, target in enumerate(SESSION_TARGETS):
            policy = RuleBasedSelfHealing() if arm == "A" else (
                GreedyPolicy() if arm == "B" else FixedPolicy())
            recovery = RecoveryStatus()
            actions = []
            responses = []
            for _ in range(target):
                # Recovery events do not consume the 20/20/15 normal-question quota.
                for _guard in range(10):
                    available = [q for q in by_form["practice"] if q.item_id not in seen]
                    if arm == "A":
                        decision = policy.choose(learner.belief, available,
                                                 len(responses), recovery)
                    else:
                        decision = policy.choose(learner.belief, available)
                    if decision.action == "QUESTION":
                        break
                    actions.append(decision.action)
                    if decision.action == "DROP_2":
                        item = next(q for q in by_form["recovery_drop2"]
                                    if q.concept == decision.concept)
                        learner.answer(item, rng)
                    else:
                        learner.resource(decision.concept, decision.action)
                else:
                    raise AssertionError("recovery action loop failed to terminate")
                item = next(q for q in available if q.item_id == decision.item_id)
                seen.add(item.item_id)
                responses.append({"item_id": item.item_id,
                                  "correct": learner.answer(item, rng),
                                  "concept": item.concept})
            sessions.append({"session": session_idx + 1, "target": target,
                             "responses": responses, "recovery_events": actions,
                             "recovery_attempts": recovery.attempts,
                             "fatigue": [rng.randint(1, 5) for _ in range(6)],
                             "fatigue_is_synthetic": True})
        post = [int(learner.assess(q, rng)) for q in by_form["posttest"]]
        participants.append({"synthetic_id": f"SYN_{p:04}", "arm": arm,
                             "pretest": pre, "sessions": sessions,
                             "posttest": post, "synthetic": True})
    result = {"schema_version": SCHEMA_VERSION, "synthetic": True,
              "seed": seed, "item_bank_hash": bank_hash(bank),
              "participants": participants,
              "warning": "SIMULATED DATA; NOT HUMAN RCT EVIDENCE"}
    audit_mock_study(result)
    return result


def bank_hash(items: list[Item]) -> str:
    return sha256(json.dumps([asdict(x) for x in items], sort_keys=True).encode()).hexdigest()


def audit_mock_study(result: dict) -> dict:
    if result.get("synthetic") is not True:
        raise ValueError("mock audit accepts only explicitly synthetic records")
    persons = result["participants"]
    counts = Counter(p["arm"] for p in persons)
    if len(set(p["synthetic_id"] for p in persons)) != len(persons):
        raise ValueError("duplicate participant identifier")
    if len(set(counts.values())) != 1 or set(counts) != set(ARMS):
        raise ValueError("unbalanced synthetic trial")
    for p in persons:
        if not p.get("synthetic") or len(p["pretest"]) != 16 or len(p["posttest"]) != 16:
            raise ValueError("invalid synthetic baseline/post outcome")
        if [len(s["responses"]) for s in p["sessions"]] != list(SESSION_TARGETS):
            raise ValueError("wrong session question quota")
        if any(len(s["fatigue"]) != 6 for s in p["sessions"]):
            raise ValueError("missing synthetic fatigue responses")
        questions = [r["item_id"] for s in p["sessions"] for r in s["responses"]]
        if len(questions) != len(set(questions)):
            raise ValueError("repeated practice item")
        for s in p["sessions"]:
            if s["recovery_attempts"] > 2:
                raise ValueError("recovery limit exceeded")
            if p["arm"] != "A" and s["recovery_events"]:
                raise ValueError("unexpected intervention in comparator arm")
    return {"participants": len(persons), "per_arm": dict(counts),
            "normal_practice_responses": len(persons) * sum(SESSION_TARGETS),
            "pretest_responses": len(persons) * 16,
            "posttest_responses": len(persons) * 16}


def write_mock_result(path: str | Path, result: dict) -> None:
    audit_mock_study(result)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError("refusing to overwrite an existing synthetic audit")
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class SyntheticAuditSQLite:
    """Append-only demo-event journal; not secure production identity storage."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("""CREATE TABLE IF NOT EXISTS synthetic_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                session_index INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(participant_id, session_index, event_type, payload)
            )""")

    def append(self, participant_id: str, session_index: int,
               event_type: str, payload: dict) -> bool:
        if not participant_id.startswith("SYN_") or not 0 <= session_index <= 3:
            raise ValueError("only synthetic participant IDs and sessions allowed")
        content = json.dumps(payload, sort_keys=True)
        with sqlite3.connect(self.path) as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO synthetic_events"
                "(participant_id,session_index,event_type,payload) VALUES(?,?,?,?)",
                (participant_id, session_index, event_type, content))
            return cur.rowcount == 1

    def read_events(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT seq,participant_id,session_index,event_type,payload "
                "FROM synthetic_events ORDER BY seq").fetchall()
        return [{"seq": seq, "synthetic_id": pid, "session": sess,
                 "type": typ, "payload": json.loads(payload)}
                for seq, pid, sess, typ, payload in rows]
