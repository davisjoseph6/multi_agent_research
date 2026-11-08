"""Synthetic-only persistence prototype for a proposed three-visit pilot.

NOT the RCTCandidateEngine, NOT a production human enrollment engine, and NOT
imported by the deployed Flask app. It does not verify staff identity, consent,
eligibility, content correctness, psychometric validity, or institutional release.

It exercises exactly-once action responses, restart recovery, and immutable
pilot-session transitions on isolated SYN_PILOT_* records. No participant
identity fields, live mode, enrollment endpoint or bearer token exist here.
Caller-provided timestamps and authorization flags are allowed ONLY for
offline synthetic testing, never as security controls on a public service.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .pilot_measurements_draft import MVAS_PROPOSED_VERSION
from .pilot_item_bank_draft import PilotDraftItemBank
from .pilot_session_flow_draft import (
    PilotSequenceError,
    PilotSessionFlow,
    answer_question,
    fatigue_deltas,
    record_mvas,
    start_visit,
)

SCHEMA_VERSION = "SYNTHETIC_ONLY_PILOT_FLOW_V1_NOT_APPROVED"
ALLOWED_STAGES = {"pretest", "practice", "posttest", "mvas_pre", "mvas_post"}


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _at(value: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if value is None else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PilotSequenceError("timestamp must be timezone-aware")
    return value


def _serialize(state: PilotSessionFlow) -> str:
    def encode_date(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    return _json({
        **asdict(state),
        "rating_timestamps": [
            [encode_date(x) for x in pair] for pair in state.rating_timestamps
        ],
        "visit_started_at": [encode_date(x) for x in state.visit_started_at],
        "visit_finished_at": [encode_date(x) for x in state.visit_finished_at],
        "last_event_at": encode_date(state.last_event_at),
    })


def _deserialize(raw: str) -> PilotSessionFlow:
    data = json.loads(raw)

    def date(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None

    data["ratings"] = tuple(tuple(row) for row in data["ratings"])
    data["rating_timestamps"] = tuple(
        tuple(date(x) for x in row) for row in data["rating_timestamps"]
    )
    data["visit_started_at"] = tuple(date(x) for x in data["visit_started_at"])
    data["visit_finished_at"] = tuple(date(x) for x in data["visit_finished_at"])
    data["last_event_at"] = date(data["last_event_at"])
    return PilotSessionFlow(**data)


class SyntheticPilotStore:
    """Local synthetic record engine; never attach to a public API or human data."""

    def __init__(self, path: str | Path, *, items_path: str | Path | None = None):
        self.question_bank = PilotDraftItemBank(items_path) if items_path is not None else None
        # A bank-bound synthetic database and the count-only fixture have
        # different schema identities; never silently mix either study mode.
        self.schema_version = (
            SCHEMA_VERSION if self.question_bank is None
            else SCHEMA_VERSION + "_95_ITEM_BANK_" + self.question_bank.sha256
        )
        self.path = Path(path)
        if self.path.is_symlink():
            raise PilotSequenceError("refuse symlink database path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # Never create a world-readable synthetic database, even briefly.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        with self._transaction() as db:
            schema_sql = """CREATE TABLE IF NOT EXISTS pilot_meta (
                id INTEGER PRIMARY KEY CHECK(id=1), version TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_people (
                pid TEXT PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_actions (
                action_id TEXT PRIMARY KEY, pid TEXT NOT NULL REFERENCES pilot_people(pid),
                public TEXT NOT NULL, offered_at TEXT NOT NULL,
                rendered_at TEXT, completed_at TEXT, response TEXT);
            CREATE TABLE IF NOT EXISTS pilot_requests (
                pid TEXT NOT NULL REFERENCES pilot_people(pid),
                request_id TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL,
                PRIMARY KEY(pid, request_id));
            CREATE TABLE IF NOT EXISTS pilot_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                pid TEXT NOT NULL REFERENCES pilot_people(pid),
                at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
            """
            # executescript() would commit the explicit initialization
            # transaction; individual statements keep schema+version atomic.
            for statement in schema_sql.split(";"):
                if statement.strip():
                    db.execute(statement)
            row = db.execute("SELECT version FROM pilot_meta WHERE id=1").fetchone()
            if row is None:
                db.execute("INSERT INTO pilot_meta VALUES(1,?)", (self.schema_version,))
            elif row["version"] != self.schema_version:
                raise PilotSequenceError("synthetic database schema mismatch; no migration")
        self.path.chmod(0o600)

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _event(db, pid: str, at: datetime, kind: str, **kwargs):
        db.execute(
            "INSERT INTO pilot_events(pid,at,kind,payload) VALUES(?,?,?,?)",
            (pid, at.isoformat(), kind, _json(kwargs)),
        )

    @staticmethod
    def _load(db, pid: str) -> PilotSessionFlow:
        if not isinstance(pid, str) or not pid.startswith("SYN_PILOT_"):
            raise PilotSequenceError("synthetic participant ID required")
        row = db.execute("SELECT state FROM pilot_people WHERE pid=?", (pid,)).fetchone()
        if row is None:
            raise PilotSequenceError("unknown synthetic participant")
        return _deserialize(row["state"])

    @staticmethod
    def _save(db, pid: str, state: PilotSessionFlow):
        db.execute("UPDATE pilot_people SET state=? WHERE pid=?", (_serialize(state), pid))

    def new_synthetic_participant(self, *, at: datetime | None = None) -> str:
        timestamp = _at(at)
        pid = "SYN_PILOT_" + uuid.uuid4().hex
        with self._transaction() as db:
            db.execute(
                "INSERT INTO pilot_people(pid,state,created_at) VALUES(?,?,?)",
                (pid, _serialize(PilotSessionFlow()), timestamp.isoformat()),
            )
            self._event(db, pid, timestamp, "synthetic_record_created")
        return pid

    def start_supervised_visit(
        self,
        pid: str,
        *,
        visit: int,
        at: datetime | None = None,
        offline_staff_authorized: bool = False,
        synthetic_release_authorized: bool = False,
    ) -> dict:
        """Offline simulation only: flags are NOT authentication or legal release."""
        timestamp = _at(at)
        with self._transaction() as db:
            state = self._load(db, pid)
            updated = start_visit(
                state, at=timestamp, visit=visit,
                staff_authorized=offline_staff_authorized,
                release_authorized=synthetic_release_authorized,
            )
            self._save(db, pid, updated)
            self._event(db, pid, timestamp, "synthetic_visit_started", visit=visit)
        return dict(accepted=True, visit=visit, stage=updated.stage)

    def next_action(self, pid: str, *, at: datetime | None = None) -> dict:
        """Offer an optional draft bank-backed MCQ, or a synthetic placeholder."""
        timestamp = _at(at)
        with self._transaction() as db:
            state = self._load(db, pid)
            if state.last_event_at is not None and timestamp < state.last_event_at:
                raise PilotSequenceError("action offered before last accepted event")
            if state.stage == "awaiting_visit":
                return dict(action="AWAITING_SUPERVISOR", visit=state.session + 1)
            if state.stage == "complete":
                return dict(action="COMPLETE")
            if state.stage not in ALLOWED_STAGES:
                raise PilotSequenceError("unsupported pilot stage")
            existing = db.execute(
                "SELECT public FROM pilot_actions WHERE pid=? AND completed_at IS NULL",
                (pid,),
            ).fetchall()
            if len(existing) > 1:
                raise PilotSequenceError("multiple incomplete actions; refuse progression")
            if existing:
                return json.loads(existing[0]["public"])
            action_id = uuid.uuid4().hex
            kind = "MVAS" if state.stage.startswith("mvas_") else "QUESTION"
            public = dict(action_id=action_id, action=kind, stage=state.stage,
                          session=state.session, index=state.index)
            if kind == "MVAS":
                public["instrument_proposed_version"] = MVAS_PROPOSED_VERSION
                public["scale"] = dict(minimum=0, maximum=100, step=1)
            elif self.question_bank is not None:
                # Public Item.public() intentionally EXCLUDES the answer key.
                public["question"] = self.question_bank.select(state).public()
                public["draft_content_not_approved"] = True
            else:
                public["synthetic_count_only"] = True
            # An Item.public() question contains tuple-valued options.
            # Persist and return exactly the same JSON-compatible action:
            # the first offer must equal any subsequent pending-action replay.
            public_json = _json(public)
            public = json.loads(public_json)
            db.execute(
                "INSERT INTO pilot_actions VALUES(?,?,?,?,NULL,NULL,NULL)",
                (action_id, pid, public_json, timestamp.isoformat()),
            )
            self._event(db, pid, timestamp, "synthetic_action_offered",
                        action_id=action_id, stage=state.stage, action_kind=kind)
            return public

    def mark_rendered(
        self, pid: str, action_id: str, *, at: datetime | None = None,
    ) -> dict:
        timestamp = _at(at)
        with self._transaction() as db:
            self._load(db, pid)
            row = db.execute(
                "SELECT offered_at,rendered_at,completed_at FROM pilot_actions "
                "WHERE pid=? AND action_id=?",
                (pid, action_id),
            ).fetchone()
            if row is None or row["completed_at"] is not None:
                raise PilotSequenceError("unknown, completed or foreign action")
            if timestamp < datetime.fromisoformat(row["offered_at"]):
                raise PilotSequenceError("render event predates offer")
            changed = db.execute(
                "UPDATE pilot_actions SET rendered_at=? "
                "WHERE pid=? AND action_id=? AND rendered_at IS NULL",
                (timestamp.isoformat(), pid, action_id),
            ).rowcount
            if changed:
                self._event(db, pid, timestamp, "synthetic_render_reported",
                            action_id=action_id)
        return dict(accepted=True, first_report=bool(changed))

    def submit(
        self,
        pid: str,
        action_id: str,
        request_id: str,
        response: dict,
        *,
        at: datetime | None = None,
    ) -> dict:
        timestamp = _at(at)
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise PilotSequenceError("valid request ID required")
        if not isinstance(action_id, str) or len(action_id) != 32:
            raise PilotSequenceError("valid action ID required")
        if not isinstance(response, dict):
            raise PilotSequenceError("response object required")
        payload = _json(dict(action_id=action_id, response=response))
        with self._transaction() as db:
            state = self._load(db, pid)
            old = db.execute(
                "SELECT payload,result FROM pilot_requests WHERE pid=? AND request_id=?",
                (pid, request_id),
            ).fetchone()
            if old is not None:
                if old["payload"] != payload:
                    raise PilotSequenceError("request ID reused with different response")
                return {**json.loads(old["result"]), "replayed": True}
            row = db.execute(
                "SELECT public,rendered_at,completed_at FROM pilot_actions "
                "WHERE pid=? AND action_id=?",
                (pid, action_id),
            ).fetchone()
            if row is None or row["completed_at"] is not None:
                raise PilotSequenceError("stale, completed or foreign action")
            if row["rendered_at"] is None:
                raise PilotSequenceError("render acknowledgement required")
            if timestamp < datetime.fromisoformat(row["rendered_at"]):
                raise PilotSequenceError("answer predates render acknowledgement")
            public = json.loads(row["public"])
            stage = public["stage"]
            if stage != state.stage or public["session"] != state.session or public["index"] != state.index:
                raise PilotSequenceError("stale pending stage")
            result_extra = {}
            recorded_response = response
            if public["action"] == "QUESTION":
                if (set(response) != {"choice_id"} or
                        type(response["choice_id"]) is not str or
                        len(response["choice_id"]) != 1):
                    raise PilotSequenceError("one choice_id string required")
                if self.question_bank is not None:
                    expected_item = self.question_bank.select(state)
                    visible = public.get("question", {})
                    if visible.get("item_id") != expected_item.item_id:
                        raise PilotSequenceError("bank item identity mismatch")
                    allowed = {key for key, _ in expected_item.options}
                    if response["choice_id"] not in allowed:
                        raise PilotSequenceError("invalid option for frozen item")
                    correct = response["choice_id"] == expected_item.answer_id
                    recorded_response = dict(choice_id=response["choice_id"],
                                             item_id=expected_item.item_id, correct=correct)
                    if stage == "practice":
                        result_extra["correct"] = correct
                elif response["choice_id"] not in "ABCD":
                    raise PilotSequenceError("one synthetic A/B/C/D answer required")
                updated = answer_question(state, at=timestamp)
            elif public["action"] == "MVAS":
                if set(response) != {"rating"}:
                    raise PilotSequenceError("one proposed M-VAS rating required")
                updated = record_mvas(state, at=timestamp, rating=response["rating"])
            else:
                raise PilotSequenceError("unsupported synthetic action")
            db.execute(
                "UPDATE pilot_actions SET completed_at=?,response=? WHERE action_id=?",
                (timestamp.isoformat(), _json(recorded_response), action_id),
            )
            self._save(db, pid, updated)
            result = dict(accepted=True, stage=updated.stage, session=updated.session,
                          **result_extra)
            db.execute(
                "INSERT INTO pilot_requests VALUES(?,?,?,?)",
                (pid, request_id, payload, _json(result)),
            )
            self._event(db, pid, timestamp, "synthetic_action_completed",
                        action_id=action_id, stage=stage, session=state.session)
        return {**result, "replayed": False}

    def scores(self, pid: str) -> dict:
        """Return counts/scores for bank-backed synthetic assessments only."""
        if self.question_bank is None:
            raise PilotSequenceError("no item bank; no graded assessment")
        with self._transaction() as db:
            self._load(db, pid)
            rows = db.execute(
                "SELECT public,response FROM pilot_actions WHERE pid=? "
                "AND completed_at IS NOT NULL ORDER BY offered_at,action_id",
                (pid,),
            ).fetchall()
        totals = {form: dict(answered=0, correct=0) for form in
                  ("pretest", "practice", "posttest")}
        ids = set()
        for row in rows:
            action = json.loads(row["public"])
            if action["action"] != "QUESTION":
                continue
            response = json.loads(row["response"])
            item_id = response["item_id"]
            if item_id in ids or item_id != action["question"]["item_id"]:
                raise PilotSequenceError("duplicate or inconsistent item score")
            ids.add(item_id)
            form = action["stage"]
            totals[form]["answered"] += 1
            totals[form]["correct"] += int(response["correct"])
        for form in ("pretest", "posttest"):
            if totals[form]["answered"] != 16:
                totals[form]["score"] = None
            else:
                totals[form]["score"] = totals[form]["correct"]
        return dict(totals, bank_sha256=self.question_bank.sha256,
                    draft_unapproved=True, synthetic_only=True)

    def snapshot(self, pid: str) -> dict:
        """Read only synthetic state, without any raw answer or personal fields."""
        with self._transaction() as db:
            state = self._load(db, pid)
            n_actions = db.execute(
                "SELECT COUNT(*) FROM pilot_actions WHERE pid=? AND completed_at IS NOT NULL",
                (pid,),
            ).fetchone()[0]
            n_events = db.execute(
                "SELECT COUNT(*) FROM pilot_events WHERE pid=?", (pid,),
            ).fetchone()[0]
        return dict(pid=pid, stage=state.stage, session=state.session,
                    index=state.index, completed_actions=n_actions,
                    event_count=n_events, ratings=state.ratings,
                    fatigue_deltas=fatigue_deltas(state),
                    visits_started=len(state.visit_started_at),
                    visits_finished=len(state.visit_finished_at),
                    fictional_only=True, approved_for_humans=False)

    def backup(self, destination: str | Path) -> dict:
        """SQLite consistent copy for *synthetic-only* test and recovery drills."""
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with sqlite3.connect(self.path) as src, sqlite3.connect(target) as dst:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise PilotSequenceError("synthetic SQLite backup integrity check failed")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return dict(sha256=sha256(target.read_bytes()).hexdigest(),
                    synthetic_only=True)
