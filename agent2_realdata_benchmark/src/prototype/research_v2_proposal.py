"""Fail-closed, SYNTHETIC-ONLY specification/executable guards for proposed V2.

Not a replacement for the frozen three-arm RCT. The requested same-learner
A/B/C sequence is a randomized CROSSOVER, not a parallel three-arm design.
No human enrollment, email sending, consent approval or public routes.

Strict design gates prevent a partial English-only 95-item bank being
misrepresented as a 261-item EN/FR, mutually disjoint, expert-reviewed bank.
An explicit, immediate DROP_2 retest is the only necessary exception to
a no-question-repeat policy, and is not a new independent assessment item.

Contact information belongs to a different institution-controlled vault.
This module never stores email addresses or creates active mail accounts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import permutations
import hashlib
import hmac
import secrets
from typing import Mapping, Sequence

from .study_v2 import BKT, CONCEPTS, RECOVERY_ACTIONS


PERIODS = ("A", "B", "C")
QUESTIONS_PER_ARM = {"pretest": 16, "practice": 55, "posttest": 16}
MIN_DISTINCT_CROSSOVER_ITEMS = 3 * sum(QUESTIONS_PER_ARM.values())  # 261
REMIND_AFTER = (timedelta(days=3), timedelta(days=6))
MAX_PAUSE = timedelta(days=14)
TOKEN_LIFETIME = timedelta(days=14)
EMAIL_TEMPLATES = {
    "en": {
        "welcome": "Welcome. Let's take the quiz.",
        "privacy": (
            "Responses are pseudonymized in the research dataset. If you opt "
            "in to email reminders, a separate, access-controlled contact "
            "service retains your email address; therefore participation "
            "is not completely anonymous to everyone."
        ),
        "continue": "Continue learning",
        "save": "Save and resume later",
        "reminder_1": "Your learning session is paused. You may resume it.",
        "reminder_2": "Your session is still incomplete. Please resume if you wish.",
        "next_arm": "You completed this study period. The next period is available.",
    },
    "fr": {
        "welcome": "Bienvenue ! Commençons le quiz.",
        "privacy": (
            "Les réponses sont pseudonymisées dans les données de recherche. "
            "Si vous acceptez les rappels par courriel, un service de contact "
            "distinct à accès restreint conserve votre adresse électronique. "
            "La participation n'est donc pas complètement anonyme pour tous."
        ),
        "continue": "Continuer l'apprentissage",
        "save": "Enregistrer et reprendre plus tard",
        "reminder_1": "Votre session est en pause. Vous pouvez la reprendre.",
        "reminder_2": "Votre session est incomplète. Vous pouvez encore la reprendre.",
        "next_arm": "Vous avez terminé cette période. La suivante est disponible.",
    },
}


class ProposedStudyError(ValueError):
    """The proposed design has not met its nonnegotiable invariants."""


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProposedStudyError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def ordered_arms(sequence: Sequence[str]) -> tuple[str, str, str]:
    result = tuple(sequence)
    if len(result) != 3 or set(result) != set(PERIODS):
        raise ProposedStudyError("one counterbalanced period for each of A, B and C")
    return result  # type: ignore[return-value]


def all_sequences() -> tuple[tuple[str, str, str], ...]:
    """Six counterbalanced sequences; allocation requires independent authority."""
    return tuple(permutations(PERIODS))


@dataclass(frozen=True)
class ReviewedItem:
    item_id: str
    form: str
    concept: str
    english_prompt: str
    french_prompt: str
    english_options: tuple[str, ...]
    french_options: tuple[str, ...]
    independently_reviewed_en: bool = False
    independently_reviewed_fr: bool = False


def validate_cross_language_bank(items: Sequence[ReviewedItem]) -> dict:
    """A human trial cannot use an incomplete/unreviewed bank or untranslated items."""
    if len(items) < MIN_DISTINCT_CROSSOVER_ITEMS:
        raise ProposedStudyError(
            "three non-repeating periods require at least 261 distinct "
            "assessment/practice questions; the draft 95-item bank is insufficient"
        )
    ids = [item.item_id for item in items]
    if any(not item_id or not isinstance(item_id, str) for item_id in ids):
        raise ProposedStudyError("every item requires a stable identifier")
    if len(set(ids)) != len(ids):
        raise ProposedStudyError("duplicate question identities in proposed crossover bank")
    if not {item.concept for item in items}.issubset(set(CONCEPTS)):
        raise ProposedStudyError("unexpected concept")
    by_form = {form: sum(item.form == form for item in items)
               for form in QUESTIONS_PER_ARM}
    for form, per_period in QUESTIONS_PER_ARM.items():
        if by_form[form] < 3 * per_period:
            raise ProposedStudyError("not enough unique " + form + " forms for all periods")
    for item in items:
        if item.form not in QUESTIONS_PER_ARM:
            raise ProposedStudyError("only assessment and practice items count toward 261")
        if (not item.english_prompt.strip() or not item.french_prompt.strip()
                or len(item.english_options) < 2
                or len(item.english_options) != len(item.french_options)
                or any(not x.strip() for x in item.english_options + item.french_options)):
            raise ProposedStudyError("question or answer translation missing")
        if not (item.independently_reviewed_en and item.independently_reviewed_fr):
            raise ProposedStudyError("unreviewed English/French content cannot be released")
    return {
        "result": "READY_FOR_ADDITIONAL_INSTITUTIONAL_REVIEW",
        "distinct_item_count": len(items),
        "lang": ["en", "fr"],
        "arms": len(PERIODS),
        "minimum": MIN_DISTINCT_CROSSOVER_ITEMS,
        "human_enrollment_authorized": False,
    }


def visible_item(item: ReviewedItem, language: str) -> dict:
    if language not in ("en", "fr"):
        raise ProposedStudyError("unsupported UI language")
    if not (item.independently_reviewed_en and item.independently_reviewed_fr):
        raise ProposedStudyError("unreviewed French/English question withheld")
    prompt, choices = (
        (item.english_prompt, item.english_options)
        if language == "en" else (item.french_prompt, item.french_options)
    )
    if not prompt.strip() or any(not c.strip() for c in choices):
        raise ProposedStudyError("cannot fall back to wrong-language question text")
    return {"item_id": item.item_id, "concept": item.concept,
            "prompt": prompt, "options": list(choices), "lang": language}


@dataclass
class PauseEpisode:
    """One inactivity episode; scheduler calls it through verified durable storage."""
    paused_at: datetime
    last_activity_at: datetime
    reminders_sent: set[int] = field(default_factory=set)
    first_reminder_at: datetime | None = None
    email_opt_in: bool = False
    withdrawn: bool = False
    completed: bool = False

    def due(self, now: datetime) -> tuple[int, ...]:
        when = utc(now)
        started = utc(self.paused_at)
        if when < started:
            raise ProposedStudyError("clock predates pause")
        if (self.withdrawn or self.completed or not self.email_opt_in
                or utc(self.last_activity_at) > started
                or when - started > MAX_PAUSE):
            return ()
        # Dispatch at most one email at a time. If a worker is late,
        # the second reminder is still separated by three actual days,
        # rather than sending two simultaneous messages on day six.
        if 1 not in self.reminders_sent:
            return (1,) if when - started >= REMIND_AFTER[0] else ()
        if 2 not in self.reminders_sent and self.first_reminder_at is not None:
            return (2,) if when - utc(self.first_reminder_at) >= timedelta(days=3) else ()
        return ()

    def claim(self, number: int, now: datetime) -> None:
        if number not in self.due(now):
            raise ProposedStudyError("duplicate, premature, or unauthorized reminder")
        self.reminders_sent.add(number)
        if number == 1:
            self.first_reminder_at = utc(now)

    def may_resume(self, now: datetime) -> bool:
        return (not self.withdrawn and not self.completed
                and utc(now) >= utc(self.paused_at)
                and utc(now) - utc(self.paused_at) <= MAX_PAUSE)


@dataclass
class CrossoverProgress:
    """Pure, per-participant synthetic state machine; identity vault is separate."""
    sequence: tuple[str, str, str]
    current_period: int = 0
    finished_periods: set[str] = field(default_factory=set)
    exposed_assessment_practice_ids: set[str] = field(default_factory=set)
    seen_in_current_period: set[str] = field(default_factory=set)
    form_counts_current_period: dict[str, int] = field(default_factory=lambda: {
        form: 0 for form in QUESTIONS_PER_ARM
    })
    active_token_hash: str | None = None
    token_expires_at: datetime | None = None

    def __post_init__(self):
        self.sequence = ordered_arms(self.sequence)
        if self.current_period not in (0, 1, 2, 3):
            raise ProposedStudyError("invalid crossover period")

    @property
    def current_arm(self) -> str | None:
        return self.sequence[self.current_period] if self.current_period < 3 else None

    def issue_next_token(self, now: datetime, *, prior_period_complete: bool) -> str:
        if self.current_period >= 3:
            raise ProposedStudyError("all periods finished")
        if self.current_period > 0 and not prior_period_complete:
            raise ProposedStudyError("cannot enter next arm before completing current arm")
        if self.active_token_hash is not None:
            raise ProposedStudyError("one active token per learner and period")
        token = secrets.token_urlsafe(32)
        self.active_token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.token_expires_at = utc(now) + TOKEN_LIFETIME
        return token

    def authenticate(self, token: str, now: datetime) -> bool:
        if (not isinstance(token, str) or self.active_token_hash is None
                or self.token_expires_at is None or utc(now) > self.token_expires_at):
            return False
        return hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), self.active_token_hash
        )

    def record_question(self, item_id: str, *, kind: str = "QUESTION",
                        form: str = "practice",
                        immediately_previous_wrong_id: str | None = None) -> None:
        if self.active_token_hash is None:
            raise ProposedStudyError("period not opened")
        if kind == "DROP_2":
            # A re-attempt of the just-answered incorrect question is the
            # explicit exception required by the user's DROP_2 semantics.
            if (self.current_arm != "A" or item_id != immediately_previous_wrong_id
                    or item_id not in self.seen_in_current_period):
                raise ProposedStudyError("DROP_2 retry must target current arm's last wrong item")
            return
        if (kind != "QUESTION" or not item_id
                or item_id in self.exposed_assessment_practice_ids):
            raise ProposedStudyError("normal question cannot repeat in any period")
        if form not in QUESTIONS_PER_ARM:
            raise ProposedStudyError("question has unknown independent form")
        if self.form_counts_current_period[form] >= QUESTIONS_PER_ARM[form]:
            raise ProposedStudyError("period form budget exhausted")
        self.exposed_assessment_practice_ids.add(item_id)
        self.seen_in_current_period.add(item_id)
        self.form_counts_current_period[form] += 1

    def complete_period(self, *, observed_unique_forms: Mapping[str, int]) -> None:
        if self.active_token_hash is None or self.current_arm is None:
            raise ProposedStudyError("period not open")
        if (dict(observed_unique_forms) != QUESTIONS_PER_ARM
                or self.form_counts_current_period != QUESTIONS_PER_ARM
                or len(self.seen_in_current_period) != 87):
            raise ProposedStudyError("all independent pretest/practice/posttest items required")
        self.finished_periods.add(self.current_arm)
        self.current_period += 1
        self.active_token_hash = None
        self.token_expires_at = None
        self.seen_in_current_period.clear()
        self.form_counts_current_period = {
            form: 0 for form in QUESTIONS_PER_ARM
        }


@dataclass
class TwoWrongRecovery:
    """Separate experimental rule. Only active in Arm A's practice window."""
    wrong_streak: int = 0
    offered_in_visit: int = 0
    pending_recovery: bool = False

    def observe_question(self, *, arm: str, stage: str, correct: bool) -> bool:
        if arm != "A" or stage != "practice":
            return False
        if self.pending_recovery:
            raise ProposedStudyError("recovery must precede next question or fatigue rating")
        self.wrong_streak = 0 if correct else self.wrong_streak + 1
        if self.wrong_streak >= 2:
            self.pending_recovery = True
        return self.pending_recovery

    def choose_recovery(self) -> str:
        if not self.pending_recovery:
            raise ProposedStudyError("two consecutive wrong practice answers required")
        # Deterministic type rotation is explicitly a rule-based intervention
        # and NOT a POMCP-selected action. Budget can reach 10 in a 20-Q visit.
        return RECOVERY_ACTIONS[self.offered_in_visit % len(RECOVERY_ACTIONS)]

    def acknowledge_recovery(self, kind: str) -> None:
        if kind != self.choose_recovery():
            raise ProposedStudyError("recovery type does not match mandated action")
        self.pending_recovery = False
        self.offered_in_visit += 1
        self.wrong_streak = 0

    def fatigue_allowed(self) -> bool:
        return not self.pending_recovery


def bkt_trace(questions: Sequence[Mapping[str, object]]) -> dict:
    """Live BKT state after every valid observed answer, not posttest scores.

    Source events are privately authenticated and already scored by the
    study engine. Text-resource acknowledgement has no correctness evidence.
    """
    mastery = {concept: .2 for concept in CONCEPTS}
    trace = [{"answered": 0, "mastery": dict(mastery)}]
    learner = BKT()
    answered = 0
    for event in questions:
        stage = event.get("stage")
        kind = event.get("action")
        if kind not in ("QUESTION", "DROP_2"):
            continue
        if stage not in ("pretest", "practice", "posttest"):
            raise ProposedStudyError("unexpected BKT observation stage")
        concept, correct = event.get("concept"), event.get("correct")
        if concept not in CONCEPTS or type(correct) is not bool:
            raise ProposedStudyError("BKT requires a scored answer and known concept")
        # Existing V3 convention: pretest posterior evidence only; practice
        # applies BKT posterior+learn; posttest is independent measurement.
        if stage == "pretest":
            mastery[concept] = learner.posterior(mastery[concept], correct)
        elif stage == "practice":
            mastery[concept] = learner.update(mastery[concept], correct)
        answered += 1
        trace.append({"answered": answered, "mastery": dict(mastery)})
    return {
        "method": "BKT_PROVISIONAL_PARAMETERS",
        "points": trace,
        "concepts": list(CONCEPTS),
        "note": (
            "Model-estimated mastery, not observed pre/post scores. A completed "
            "text hint does not prove restoration of mastery."
        ),
        "human_enrollment_authorized": False,
    }
