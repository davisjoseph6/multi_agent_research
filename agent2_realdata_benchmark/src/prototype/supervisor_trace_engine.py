"""Supervisor 2026-11-11 *parallel-arm* deterministic trace policy.

This is an offline reference adapter for the existing three-arm architecture,
not a public enrollment server or a replacement for validated human-study
content. It follows participant_scenarios.docx and scenario_traces.csv.

The original study_v2.BKT computes the same four-parameter Bayesian update.
Pre/post screening data is not a source of adaptive question candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .study_v2 import BKT

CONCEPT_IDS = tuple(f"C{i}" for i in range(1, 9))
SESSION_BLOCKS = (20, 20, 15)
RECOVERY_SEQUENCE = (
    "CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT",
)


@dataclass
class SupervisorTraceEngine:
    """One fictional learner's adaptive selection and recovery state."""

    arm: str
    mastery: dict[str, float]
    bloom: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CONCEPT_IDS, 1))
    correct_streak: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CONCEPT_IDS, 0))
    wrong_streak: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CONCEPT_IDS, 0))
    recovery_wrong: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CONCEPT_IDS, 0))
    seen: dict[str, int] = field(default_factory=dict)
    last_failed: dict[str, str] = field(default_factory=dict)
    session_peak: dict[str, float] = field(default_factory=dict)
    per_concept_recovery: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CONCEPT_IDS, 0))
    nonrecoverable: set[str] = field(default_factory=set)
    attempts_session: int = 0
    session: int = 1
    question_in_session: int = 0
    elapsed: int = 0
    pending: list[dict] = field(default_factory=list)
    current_recovery: str | None = None
    last_recovery_trigger: str | None = None

    def __post_init__(self):
        if self.arm not in ("A", "B", "C"):
            raise ValueError("exactly one fixed A/B/C assignment required")
        if set(self.mastery) != set(CONCEPT_IDS) or any(
                not 0 <= m <= 1 for m in self.mastery.values()):
            raise ValueError("one valid initial mastery per concept required")
        if set(self.bloom) != set(CONCEPT_IDS) or any(
                type(level) is not int or not 1 <= level <= 6
                for level in self.bloom.values()):
            raise ValueError("Bloom level must be 1 through 6")
        if self.elapsed == 0 and any(
                level != 1 for level in self.bloom.values()):
            raise ValueError("all Bloom levels must initially equal L1")
        if not self.session_peak:
            self.session_peak = self.mastery.copy()
        elif (set(self.session_peak) != set(CONCEPT_IDS)
              or any(not 0 <= p <= 1 for p in self.session_peak.values())):
            raise ValueError("invalid preserved session mastery peaks")

    def snapshot(self) -> dict:
        """JSON-serializable state for atomic persistence after each step."""
        return {
            "arm": self.arm, "mastery": dict(self.mastery),
            "bloom": dict(self.bloom),
            "correct_streak": dict(self.correct_streak),
            "wrong_streak": dict(self.wrong_streak),
            "recovery_wrong": dict(self.recovery_wrong),
            "seen": dict(self.seen), "last_failed": dict(self.last_failed),
            "session_peak": dict(self.session_peak),
            "per_concept_recovery": dict(self.per_concept_recovery),
            "nonrecoverable": sorted(self.nonrecoverable),
            "attempts_session": self.attempts_session,
            "session": self.session, "question_in_session": self.question_in_session,
            "elapsed": self.elapsed, "pending": list(self.pending),
            "current_recovery": self.current_recovery,
            "last_recovery_trigger": self.last_recovery_trigger,
        }

    @classmethod
    def restore(cls, snapshot: dict) -> "SupervisorTraceEngine":
        """Rebuild a pending recovery without modifying its action order."""
        if type(snapshot) is not dict:
            raise ValueError("invalid state snapshot")
        keys = set(cls("A", dict.fromkeys(CONCEPT_IDS, .20)).snapshot())
        if set(snapshot) != keys:
            raise ValueError("snapshot has missing or unexpected keys")
        data = dict(snapshot)
        data["nonrecoverable"] = set(data["nonrecoverable"])
        instance = cls(**data)
        if (instance.session not in (1, 2, 3)
                or not 0 <= instance.question_in_session <=
                SESSION_BLOCKS[instance.session - 1]
                or any(step.get("action") not in RECOVERY_SEQUENCE
                       for step in instance.pending)):
            raise ValueError("corrupted supervisor state snapshot")
        return instance

    @property
    def degradation(self) -> float:
        """Monitoring ONLY; never a recovery trigger."""
        return 1 - sum(self.mastery.values()) / 8

    def new_session(self, n: int) -> None:
        if n != self.session + 1 or n not in (2, 3):
            raise ValueError("sessions must advance exactly once")
        if self.question_in_session != SESSION_BLOCKS[self.session - 1]:
            raise ValueError("cannot skip an unfinished regular quiz block")
        if self.pending:
            raise ValueError("cannot interrupt unfinished recovery at session end")
        self.session = n
        self.question_in_session = 0
        self.attempts_session = 0
        self.recovery_wrong = dict.fromkeys(CONCEPT_IDS, 0)
        self.last_failed = {}
        self.session_peak = self.mastery.copy()

    @staticmethod
    def question_id(concept: str, level: int, index: int) -> str:
        return f"QZ_{concept}_L{level}_{index:02d}"

    @staticmethod
    def bank_size(level: int) -> int:
        if not 1 <= level <= 6:
            raise ValueError("unknown Bloom level")
        return 6 if level in (1, 2) else 3

    def unseen(self, concept: str, level: int) -> list[str]:
        if concept not in CONCEPT_IDS:
            raise ValueError("unknown concept")
        return [
            self.question_id(concept, level, i)
            for i in range(1, self.bank_size(level) + 1)
            if self.question_id(concept, level, i) not in self.seen
        ]

    def greedy(self) -> dict:
        skipped = []
        for c in sorted(CONCEPT_IDS, key=lambda c: (
                self.mastery[c], int(c[1:]))):
            available = self.unseen(c, self.bloom[c])
            if available:
                return dict(
                    action="QUESTION", qid=available[0], concept=c,
                    level=self.bloom[c], mode=(
                        "NOMINAL" if self.arm == "A" else "GREEDY"),
                    skipped_concepts=tuple(skipped),
                )
            skipped.append(c)
        # Rule 4b: repeat the least-recently shown *normal* question among
        # the 8 concepts at their current Bloom levels. Socratic re-attempts
        # do not refresh an earlier normal-question LRU timestamp, matching
        # the authoritative reference traces.
        candidates = [
            self.question_id(c, self.bloom[c], i)
            for c in CONCEPT_IDS
            for i in range(1, self.bank_size(self.bloom[c]) + 1)
        ]
        chosen = min(candidates, key=lambda q: (self.seen[q], q))
        return dict(
            action="QUESTION", qid=chosen,
            concept=chosen.split("_")[1],
            level=int(chosen.split("_")[2][1:]),
            mode="NOMINAL" if self.arm == "A" else "GREEDY",
            repeated_by_rule_4b=True,
        )

    def fixed(self) -> dict:
        index = sum(SESSION_BLOCKS[:self.session - 1]) + self.question_in_session
        remainder = index
        # Group C: the original _01.._03 items only, all L1 by concept,
        # then all L2, then L3, across the whole 55-question sequence.
        for level in range(1, 7):
            for concept in CONCEPT_IDS:
                if remainder < 3:
                    return dict(
                        action="QUESTION",
                        qid=self.question_id(concept, level, remainder + 1),
                        concept=concept, level=level, mode="FIXED",
                    )
                remainder -= 3
        raise AssertionError("fixed sequence index outside bank")

    def next_action(self) -> dict | None:
        if self.pending:
            return self.pending[0]
        if self.question_in_session >= SESSION_BLOCKS[self.session - 1]:
            return None
        return self.fixed() if self.arm == "C" else self.greedy()

    def _use(self, item_id: str) -> None:
        self.elapsed += 1
        self.seen[item_id] = self.elapsed

    def submit(self, answer: str) -> dict:
        """Apply a trusted *scripted* answer to the pending step.

        This is not a student endpoint. Genuine answer grading and event
        persistence belong to an authenticated server.
        """
        step = self.next_action()
        if step is None:
            raise ValueError("regular block finished")
        if self.pending:
            self.pending.pop(0)
        c, action = step["concept"], step["action"]
        if action == "QUESTION":
            if answer not in ("correct", "wrong"):
                raise ValueError("scored regular question required")
            self.question_in_session += 1
            self._use(step["qid"])
            self.mastery[c] = BKT().update(
                self.mastery[c], answer == "correct")
            if answer == "correct":
                self.correct_streak[c] += 1
                self.wrong_streak[c] = 0
                self.recovery_wrong[c] = 0
            else:
                self.wrong_streak[c] += 1
                self.correct_streak[c] = 0
                self.recovery_wrong[c] += 1
                self.last_failed[c] = step["qid"]
            if (answer == "correct" and self.correct_streak[c] >= 2
                    and self.bloom[c] < 6):
                self.bloom[c] += 1
                self.correct_streak[c] = 0
                self.wrong_streak[c] = 0
            elif (answer == "wrong" and self.wrong_streak[c] >= 2
                    and self.bloom[c] > 1):
                self.bloom[c] -= 1
                self.correct_streak[c] = 0
                self.wrong_streak[c] = 0
            self.session_peak[c] = max(
                self.session_peak[c], self.mastery[c])
            if self.arm == "A":
                trigger = None
                if (self.recovery_wrong[c] >= 2
                        and self.session_peak[c] - self.mastery[c] >= 0.25):
                    trigger = "5a"
                elif self.recovery_wrong[c] >= 3:
                    trigger = "5b"
                if (trigger and self.attempts_session < 2
                        and self.per_concept_recovery[c] < 2
                        and c not in self.nonrecoverable):
                    self.start_recovery(c, trigger)
        elif action in ("DROP_2", "SOCRATIC_HINT"):
            if answer not in ("correct", "wrong"):
                raise ValueError("graded recovery re-attempt required")
            if action != "SOCRATIC_HINT" or step["qid"] not in self.seen:
                self._use(step["qid"])
            # Recovery answers update BKT but never the block counter or
            # Bloom-level promotion/demotion streaks (Rule 1).
            self.mastery[c] = BKT().update(
                self.mastery[c], answer == "correct")
            if action == "SOCRATIC_HINT":
                if (self.mastery[c] < 0.50
                        and self.per_concept_recovery[c] >= 2):
                    self.nonrecoverable.add(c)
                    self.bloom[c] = 1
                self.recovery_wrong[c] = 0
                self.session_peak[c] = self.mastery[c]
                self.current_recovery = None
        elif action in ("CONCEPT_SUMMARY", "WORKED_EXAMPLE"):
            if answer != "":
                raise ValueError("reading resource has no scored answer")
        else:
            raise ValueError("unknown action type")
        return step

    def start_recovery(self, concept: str, trigger: str) -> None:
        if self.arm != "A" or self.pending:
            raise ValueError("cannot start overlapping recovery")
        self.attempts_session += 1
        self.per_concept_recovery[concept] += 1
        self.current_recovery = concept
        self.last_recovery_trigger = trigger
        unseen_l1 = self.unseen(concept, 1)
        drop = unseen_l1[0] if unseen_l1 else min(
            (self.question_id(concept, 1, i) for i in range(1, 7)),
            key=lambda q: self.seen[q],
        )
        socratic = self.last_failed.get(concept)
        if not socratic:
            socratic = unseen_l1[0] if unseen_l1 else min(
                (self.question_id(concept, 1, i) for i in range(1, 7)),
                key=lambda q: self.seen[q],
            )
        self.pending = [
            dict(action="CONCEPT_SUMMARY", qid="—", concept=concept,
                 level=self.bloom[concept], mode="RECOVERY"),
            dict(action="DROP_2", qid=drop, concept=concept,
                 level=1, mode="RECOVERY"),
            dict(action="WORKED_EXAMPLE", qid="—", concept=concept,
                 level=2, mode="RECOVERY"),
            dict(action="SOCRATIC_HINT", qid=socratic, concept=concept,
                 level=int(socratic.split("_")[2][1:]), mode="RECOVERY"),
        ]
