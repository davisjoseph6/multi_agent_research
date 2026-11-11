"""Crash-consistent three-period crossover rehearsal, WITHOUT human enrollment.

Fictional participant references and a separate fictional SQLite DB only.
An approved, reviewed 261-item bilingual bank is NOT provided by this module.
The caller is a trusted offline synthetic runner, not a public web endpoint.
This code must not be used as an authenticating production participant server.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3

from .research_v2_proposal import (
    QUESTIONS_PER_ARM, ProposedStudyError, ordered_arms, utc, bkt_trace,
)
from .study_v2 import CONCEPTS, RECOVERY_ACTIONS


TOKEN_TTL = timedelta(days=14)
PAUSE_MAX = timedelta(days=14)


def _iso(at: datetime) -> str:
    return utc(at).isoformat()


def _parse(text: str) -> datetime:
    return datetime.fromisoformat(text)


class FictionalCrossoverStore:
    """One-time unique questions across arms, sequence barriers, durable tokens."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.name != "fictional_crossover.sqlite3" or self.path.is_symlink():
            raise ProposedStudyError("isolated fictional_crossover.sqlite3 required")
        if not self.path.parent.is_dir():
            raise ProposedStudyError("existing isolated fictional directory required")
        with self._transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fictional_learners(
                    ref TEXT PRIMARY KEY,
                    sequence TEXT NOT NULL,
                    period INTEGER NOT NULL DEFAULT 0,
                    token_hash TEXT,
                    expires TEXT,
                    paused_at TEXT,
                    last_wrong TEXT,
                    wrong_streak INTEGER NOT NULL DEFAULT 0,
                    recovery_pending TEXT,
                    recovery_completed INTEGER NOT NULL DEFAULT 0,
                    awaiting_continue INTEGER NOT NULL DEFAULT 0,
                    withdrawn INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS exposures(
                    ref TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    period INTEGER NOT NULL,
                    form TEXT NOT NULL,
                    concept TEXT,
                    selected_index INTEGER CHECK(selected_index BETWEEN 0 AND 3),
                    correct INTEGER NOT NULL,
                    PRIMARY KEY(ref,item_id),
                    FOREIGN KEY(ref) REFERENCES fictional_learners(ref)
                );
                CREATE TABLE IF NOT EXISTS submissions(
                    ref TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    result TEXT NOT NULL,
                    PRIMARY KEY(ref,request_id)
                );
            """)
            schema = {r["name"] for r in db.execute("PRAGMA table_info(fictional_learners)")}
            exposures_schema = {
                r["name"] for r in db.execute("PRAGMA table_info(exposures)")
            }
            if (not {"wrong_streak", "recovery_pending", "recovery_completed",
                     "awaiting_continue"}.issubset(schema)
                    or not {"concept", "selected_index"}.issubset(exposures_schema)):
                raise ProposedStudyError(
                    "old fictional crossover schema unsupported; use a new isolated test DB"
                )
        os.chmod(self.path, 0o600)

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _ref(ref: str):
        if not isinstance(ref, str) or not re.fullmatch(
                r"SYN_CROSSOVER_[A-Za-z0-9_-]{1,64}", ref):
            raise ProposedStudyError("fictional learner reference required")

    def enroll_fictional(self, ref: str, sequence: tuple[str, str, str]):
        self._ref(ref)
        order = ordered_arms(sequence)
        with self._transaction() as db:
            db.execute(
                "INSERT INTO fictional_learners(ref,sequence) VALUES(?,?)",
                (ref, "".join(order)),
            )

    @staticmethod
    def _state(db, ref: str):
        row = db.execute(
            "SELECT * FROM fictional_learners WHERE ref=?", (ref,)
        ).fetchone()
        if row is None or row["withdrawn"]:
            raise ProposedStudyError("fictional learner missing or withdrawn")
        return row

    @staticmethod
    def _authorize(row, token: str, at: datetime):
        if (not isinstance(token, str) or not row["token_hash"]
                or not row["expires"] or utc(at) > _parse(row["expires"])
                or not hmac.compare_digest(
                    hashlib.sha256(token.encode()).hexdigest(), row["token_hash"]
                )):
            raise ProposedStudyError("invalid or expired period token")
        if row["paused_at"]:
            raise ProposedStudyError("fictional study period is paused")

    def issue_token(self, ref: str, at: datetime) -> str:
        self._ref(ref)
        token = secrets.token_urlsafe(32)
        with self._transaction() as db:
            row = self._state(db, ref)
            if row["period"] >= 3 or row["token_hash"]:
                raise ProposedStudyError("period is already active or all periods complete")
            db.execute(
                "UPDATE fictional_learners SET token_hash=?,expires=? WHERE ref=?",
                (hashlib.sha256(token.encode()).hexdigest(), _iso(utc(at) + TOKEN_TTL), ref),
            )
        return token

    def rotate_token(self, ref: str, at: datetime, *,
                     contact_identity_verified: bool) -> str:
        """Fictional credential renewal; an external controller must verify identity."""
        self._ref(ref)
        if contact_identity_verified is not True:
            raise ProposedStudyError("independent contact identity verification required")
        token = secrets.token_urlsafe(32)
        with self._transaction() as db:
            row = self._state(db, ref)
            if row["period"] >= 3 or not row["token_hash"]:
                raise ProposedStudyError("active period required for credential rotation")
            db.execute(
                "UPDATE fictional_learners SET token_hash=?,expires=? WHERE ref=?",
                (hashlib.sha256(token.encode()).hexdigest(), _iso(utc(at) + TOKEN_TTL), ref),
            )
        return token

    @staticmethod
    def _counts(db, ref: str, period: int):
        return {
            form: db.execute(
                "SELECT COUNT(*) FROM exposures WHERE ref=? AND period=? AND form=?",
                (ref, period, form),
            ).fetchone()[0]
            for form in QUESTIONS_PER_ARM
        }

    def record(self, ref: str, token: str, *, request_id: str,
               item_id: str, form: str, correct: bool, at: datetime,
               kind: str = "QUESTION",
               concept: str | None = None,
               selected_index: int | None = None) -> dict:
        """The trusted fictional grader supplies scored observations.

        Request-ID replay is safe only when the entire payload matches.
        DROP_2 is one immediate instructional retry, not new mastery evidence.
        """
        self._ref(ref)
        if (not isinstance(request_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{8,80}", request_id)):
            raise ProposedStudyError("unique synthetic request id required")
        if (not isinstance(item_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_:-]{1,100}", item_id)
                or type(correct) is not bool
                or kind not in ("QUESTION", "DROP_2")):
            raise ProposedStudyError("invalid scored fictional question")
        if kind == "QUESTION" and form not in QUESTIONS_PER_ARM:
            raise ProposedStudyError("unknown form")
        if concept is not None and concept not in CONCEPTS:
            raise ProposedStudyError("unexpected concept metadata")
        if selected_index is not None and (
                type(selected_index) is not int or not 0 <= selected_index <= 3):
            raise ProposedStudyError("invalid answer-choice index")
        if kind == "DROP_2" and not correct:
            raise ProposedStudyError("DROP_2 only completes after correct retry")
        payload = json.dumps(
            [item_id, form, correct, kind, concept, selected_index],
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            prior = db.execute(
                "SELECT fingerprint,result FROM submissions WHERE ref=? AND request_id=?",
                (ref, request_id),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(prior["fingerprint"], fingerprint):
                    raise ProposedStudyError("request replay changed the scored response")
                return dict(json.loads(prior["result"])) | {"replayed": True}
            if row["period"] >= 3:
                raise ProposedStudyError("all periods complete")
            arm = row["sequence"][row["period"]]
            if row["awaiting_continue"]:
                raise ProposedStudyError("learner must choose continue or pause after recovery")
            if kind == "DROP_2":
                if (arm != "A" or form != "practice"
                        or row["recovery_pending"] != "DROP_2"
                        or row["last_wrong"] != item_id):
                    raise ProposedStudyError(
                        "DROP_2 requires the second consecutive wrong Arm A item"
                    )
                db.execute(
                    "UPDATE fictional_learners SET last_wrong=NULL,wrong_streak=0,"
                    "recovery_pending=NULL,awaiting_continue=1,"
                    "recovery_completed=recovery_completed+1 WHERE ref=?", (ref,)
                )
                counted = False
            else:
                if row["recovery_pending"] is not None:
                    raise ProposedStudyError(
                        "recovery must complete before another question or fatigue"
                    )
                counts = self._counts(db, ref, row["period"])
                if counts[form] >= QUESTIONS_PER_ARM[form]:
                    raise ProposedStudyError("period form exhausted")
                if form == "practice" and counts["pretest"] < 16:
                    raise ProposedStudyError("complete 16 pretest items before practice")
                if form == "posttest" and counts["practice"] < 55:
                    raise ProposedStudyError("complete 55 practice items before posttest")
                try:
                    db.execute(
                        "INSERT INTO exposures(ref,item_id,period,form,concept,selected_index,correct)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (ref, item_id, row["period"], form, concept,
                         selected_index, int(correct)),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ProposedStudyError("question repeated across periods") from exc
                streak = (row["wrong_streak"] + 1 if not correct else 0
                          ) if arm == "A" and form == "practice" else 0
                recovery = (RECOVERY_ACTIONS[row["recovery_completed"] % len(RECOVERY_ACTIONS)]
                            if streak >= 2 else None)
                db.execute(
                    "UPDATE fictional_learners SET last_wrong=?,wrong_streak=?,"
                    "recovery_pending=? WHERE ref=?",
                    (item_id if arm == "A" and form == "practice" and not correct
                     else None, streak, recovery, ref),
                )
                counted = True
            result = {
                "accepted": True, "replayed": False, "counted": counted,
                "synthetic_only": True,
            }
            if kind == "QUESTION" and recovery is not None:
                result["recovery_required"] = recovery
            db.execute(
                "INSERT INTO submissions(ref,request_id,fingerprint,result) "
                "VALUES(?,?,?,?)",
                (ref, request_id, fingerprint, json.dumps(result, sort_keys=True)),
            )
            return result



    def mastery_trace(self, ref: str, token: str, at: datetime) -> dict:
        """Current-period provisional eight-concept BKT, never a causal estimate.

        Only trusted server-scored observations with known concept metadata are
        eligible. The 16-item pre/post observed scores remain independent of
        BKT and withheld until each assessment is fully completed. This is an
        authenticated fictional record reader, not a public dashboard route.
        """
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            if row["period"] >= 3:
                raise ProposedStudyError("completed period token is invalid")
            answers = db.execute(
                "SELECT form,concept,correct FROM exposures "
                "WHERE ref=? AND period=? ORDER BY rowid",
                (ref, row["period"]),
            ).fetchall()
            if any(r["concept"] not in CONCEPTS for r in answers):
                raise ProposedStudyError(
                    "cannot estimate BKT without trusted concept metadata"
                )
            events = [
                {"action": "QUESTION", "stage": r["form"],
                 "concept": r["concept"], "correct": bool(r["correct"])}
                for r in answers
            ]
            report = bkt_trace(events)
            report["independent_scores"] = {
                form: (
                    sum(int(r["correct"]) for r in answers if r["form"] == form)
                    if sum(r["form"] == form for r in answers)
                    == QUESTIONS_PER_ARM[form] else None
                )
                for form in ("pretest", "posttest")
            }
            report.update(period_index=row["period"], synthetic_only=True)
            return report

    def pending_recovery(self, ref: str) -> dict:
        """Private offline operator state; never exposed as participant auth."""
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            wrong = None
            if row["recovery_pending"] and row["last_wrong"]:
                wrong = db.execute(
                    "SELECT selected_index FROM exposures WHERE ref=? AND item_id=?",
                    (ref, row["last_wrong"]),
                ).fetchone()
            return {
                "action": row["recovery_pending"],
                "target_item_id": row["last_wrong"] if row["recovery_pending"] else None,
                "wrong_selected_index": wrong["selected_index"] if wrong else None,
                "awaiting_continue": bool(row["awaiting_continue"]),
                "synthetic_only": True,
            }

    def acknowledge_recovery(self, ref: str, token: str, *, request_id: str,
                             kind: str, at: datetime) -> dict:
        """Complete a specific non-DROP_2 intervention before any next question.

        Text acknowledgments never change BKT mastery: they are not scored
        independent observations. The trusted fictional caller provides kind.
        """
        self._ref(ref)
        if (not isinstance(request_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id)
                or kind not in RECOVERY_ACTIONS or kind == "DROP_2"):
            raise ProposedStudyError("invalid fictional recovery acknowledgment")
        fingerprint = hashlib.sha256(("RESOURCE:" + kind).encode()).hexdigest()
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            prior = db.execute(
                "SELECT fingerprint,result FROM submissions WHERE ref=? AND request_id=?",
                (ref, request_id),
            ).fetchone()
            if prior:
                if not hmac.compare_digest(prior["fingerprint"], fingerprint):
                    raise ProposedStudyError("request replay changed the recovery response")
                return dict(json.loads(prior["result"])) | {"replayed": True}
            if row["recovery_pending"] != kind or row["awaiting_continue"]:
                raise ProposedStudyError("recovery type is not currently pending")
            db.execute(
                "UPDATE fictional_learners SET recovery_pending=NULL,wrong_streak=0,"
                "last_wrong=NULL,awaiting_continue=1,"
                "recovery_completed=recovery_completed+1 WHERE ref=?", (ref,),
            )
            result = {"accepted": True, "replayed": False,
                      "counted": False, "synthetic_only": True}
            db.execute(
                "INSERT INTO submissions(ref,request_id,fingerprint,result) VALUES(?,?,?,?)",
                (ref, request_id, fingerprint, json.dumps(result, sort_keys=True)),
            )
            return result

    def decide_after_recovery(self, ref: str, token: str, *, decision: str,
                              at: datetime) -> dict:
        """An explicit learner decision is required after every intervention."""
        self._ref(ref)
        if decision not in ("continue", "pause"):
            raise ProposedStudyError("choose continue or pause")
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            if not row["awaiting_continue"] or row["recovery_pending"]:
                raise ProposedStudyError("no completed recovery awaiting learner decision")
            db.execute(
                "UPDATE fictional_learners SET awaiting_continue=0,paused_at=? WHERE ref=?",
                (_iso(at) if decision == "pause" else None, ref),
            )
        return {"accepted": True, "paused": decision == "pause",
                "synthetic_only": True}

    def finish_period(self, ref: str, token: str, at: datetime) -> int:
        """No next arm until all three independent sections are complete."""
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            if row["recovery_pending"] or row["awaiting_continue"]:
                raise ProposedStudyError("complete recovery and continuation before finishing")
            if self._counts(db, ref, row["period"]) != QUESTIONS_PER_ARM:
                raise ProposedStudyError("87 distinct items required to finish a period")
            next_period = row["period"] + 1
            db.execute(
                "UPDATE fictional_learners SET period=?,token_hash=NULL,"
                "expires=NULL,paused_at=NULL,last_wrong=NULL,"
                "wrong_streak=0,recovery_pending=NULL,recovery_completed=0,"
                "awaiting_continue=0 WHERE ref=?",
                (next_period, ref),
            )
            return next_period

    def pause(self, ref: str, token: str, at: datetime):
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            self._authorize(row, token, at)
            db.execute(
                "UPDATE fictional_learners SET paused_at=? WHERE ref=?",
                (_iso(at), ref),
            )

    def resume(self, ref: str, token: str, at: datetime):
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            if row["paused_at"] is None:
                raise ProposedStudyError("no active fictional pause")
            if not (timedelta(0) <= utc(at) - _parse(row["paused_at"]) <= PAUSE_MAX):
                raise ProposedStudyError("14-day pause interval exceeded")
            # Token must independently be valid even during a pause.
            if (not isinstance(token, str) or not row["token_hash"]
                    or not hmac.compare_digest(
                        hashlib.sha256(token.encode()).hexdigest(), row["token_hash"]
                    ) or not row["expires"] or utc(at) > _parse(row["expires"])):
                raise ProposedStudyError("renewal of expired fictional token required")
            db.execute("UPDATE fictional_learners SET paused_at=NULL WHERE ref=?", (ref,))

    def redacted_progress(self, ref: str) -> dict:
        self._ref(ref)
        with self._transaction() as db:
            row = self._state(db, ref)
            counts = (self._counts(db, ref, row["period"])
                      if row["period"] < 3 else dict(QUESTIONS_PER_ARM))
            return {
                "period_index": row["period"],
                "counts": counts,
                "paused": row["paused_at"] is not None,
                "period_token_active": row["token_hash"] is not None,
                "recovery_due": bool(row["recovery_pending"]),
                "awaiting_continue": bool(row["awaiting_continue"]),
                "finished": row["period"] == 3,
                "synthetic_only": True,
            }
