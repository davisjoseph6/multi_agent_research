"""Transactional synthetic-only protocol engine for historical three-arm study.

This is NOT an approved human-trial server. No HTTP routes or participant
credentials are supplied here; it can only be used locally through Python.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
from typing import Any

from .study_v2 import (
    ARMS, BKT, Belief, CONCEPTS, FixedPolicy, GreedyPolicy, Item,
    RecoveryStatus, RuleBasedSelfHealing, SESSION_TARGETS, bank_hash,
    validate_bank,
)


class ProtocolError(ValueError):
    pass


def _json(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


class SyntheticProtocolEngine:
    """Exactly-once synthetic responses, trial phases, durable pending actions.

    All caller IDs must be SYN_-prefixed, so accidental human enrollment fails.
    For production, independent authentication, consent and governance are needed.
    """

    def __init__(self, path: str | Path, bank: list[Item]):
        validate_bank(bank, full=True)
        self.bank = {q.item_id: q for q in bank}
        self.bank_hash = bank_hash(bank)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS synthetic_participants (
                participant_id TEXT PRIMARY KEY,
                arm TEXT NOT NULL,
                stage TEXT NOT NULL,
                session INTEGER NOT NULL,
                index_in_stage INTEGER NOT NULL,
                mastery_json TEXT NOT NULL,
                used_json TEXT NOT NULL,
                recovery_json TEXT NOT NULL,
                pending_json TEXT,
                item_bank_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS synthetic_responses (
                request_id TEXT PRIMARY KEY,
                participant_id TEXT NOT NULL REFERENCES synthetic_participants(participant_id),
                request_payload TEXT NOT NULL,
                response_payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS synthetic_protocol_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL REFERENCES synthetic_participants(participant_id),
                event_json TEXT NOT NULL
            );
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def _get(self, db, participant_id):
        if not participant_id.startswith("SYN_"):
            raise ProtocolError("real participant identifiers are forbidden")
        row = db.execute("SELECT arm,stage,session,index_in_stage,mastery_json,"
                         "used_json,recovery_json,pending_json,item_bank_hash "
                         "FROM synthetic_participants WHERE participant_id=?",
                         (participant_id,)).fetchone()
        if row is None:
            raise ProtocolError("unknown synthetic participant")
        arm,stage,session,index_in_stage,mastery,used,recovery,pending,bank_version = row
        if bank_version != self.bank_hash:
            raise ProtocolError("item bank changed after enrollment")
        return dict(arm=arm, stage=stage, session=session, index=index_in_stage,
                    mastery=json.loads(mastery), used=json.loads(used),
                    recovery=json.loads(recovery),
                    pending=json.loads(pending) if pending is not None else None)

    def _save(self, db, pid, state):
        db.execute("""UPDATE synthetic_participants SET
            stage=?,session=?,index_in_stage=?,mastery_json=?,used_json=?,
            recovery_json=?,pending_json=? WHERE participant_id=?""",
            (state["stage"],state["session"],state["index"],
             _json(state["mastery"]),_json(state["used"]),_json(state["recovery"]),
             _json(state["pending"]) if state["pending"] else None, pid))

    @staticmethod
    def _event(db, pid, kind, **data):
        db.execute("INSERT INTO synthetic_protocol_events(participant_id,event_json) "
                   "VALUES(?,?)", (pid, _json(dict(type=kind, **data))))

    def enroll(self, participant_id: str, arm: str):
        if not participant_id.startswith("SYN_") or arm not in ARMS:
            raise ProtocolError("synthetic enrollment only; arm must be A, B or C")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT arm FROM synthetic_participants WHERE participant_id=?",
                                  (participant_id,)).fetchone()
            if existing:
                if existing[0] != arm:
                    raise ProtocolError("cannot change assigned arm")
                return False
            db.execute("""INSERT INTO synthetic_participants VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (participant_id,arm,"pretest",0,0,
                        _json({c:.20 for c in CONCEPTS}),_json([]),
                        _json(asdict(RecoveryStatus())),None,self.bank_hash))
            self._event(db, participant_id, "enrolled", arm=arm)
            return True

    def snapshot(self, participant_id):
        with self._connect() as db:
            s = self._get(db, participant_id)
        return {k:v for k,v in s.items() if k != "mastery"}

    def _candidate(self, s):
        form = s["stage"]
        if form in ("pretest", "posttest"):
            candidates = sorted((q for q in self.bank.values() if q.form == form),
                                key=lambda q:q.item_id)
            return dict(action="QUESTION", item_id=candidates[s["index"]].item_id,
                        concept=candidates[s["index"]].concept)
        if form == "fatigue":
            return dict(action="FATIGUE", session=s["session"], count=6)
        if form == "complete":
            return dict(action="COMPLETE")
        if form != "practice":
            raise ProtocolError("unexpected protocol state")
        candidates = [q for q in self.bank.values()
                      if q.form == "practice" and q.item_id not in s["used"]]
        belief = Belief(s["mastery"].copy())
        if s["arm"] == "A":
            status = RecoveryStatus(**s["recovery"])
            d = RuleBasedSelfHealing().choose(belief, candidates, s["index"], status)
            s["recovery"] = asdict(status)
        elif s["arm"] == "B":
            d = GreedyPolicy().choose(belief, candidates)
        else:
            d = FixedPolicy().choose(belief, candidates)
        result = dict(action=d.action, concept=d.concept, item_id=d.item_id)
        if d.action == "DROP_2":
            options = sorted((q for q in self.bank.values()
                              if q.form == "recovery_drop2" and q.concept == d.concept),
                             key=lambda q:q.item_id)
            if not options:
                raise ProtocolError("missing DROP_2 item")
            result["item_id"] = options[0].item_id
        return result

    def next_action(self, participant_id: str):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            s = self._get(db, participant_id)
            if s["pending"] is None:
                s["pending"] = self._candidate(s)
                self._event(db, participant_id, "action_selected", stage=s["stage"],
                            session=s["session"], action=s["pending"]["action"],
                            item_id=s["pending"].get("item_id"),
                            bank_hash=self.bank_hash)
                self._save(db, participant_id, s)
            action = dict(s["pending"])
            if action.get("item_id") is not None:
                action["question"] = self.bank[action["item_id"]].public()
            return action

    def _advance_stage(self, s):
        if s["stage"] == "pretest" and s["index"] == 16:
            s.update(stage="practice",session=1,index=0)
        elif s["stage"] == "practice" and s["index"] == SESSION_TARGETS[s["session"] - 1]:
            s.update(stage="fatigue",index=0)
        elif s["stage"] == "fatigue":
            if s["session"] == 3:
                s.update(stage="posttest",index=0)
            else:
                s.update(stage="practice",session=s["session"] + 1,index=0)
                s["recovery"] = asdict(RecoveryStatus())
        elif s["stage"] == "posttest" and s["index"] == 16:
            s.update(stage="complete",index=0)

    def act(self, pid: str, request_id: str, action: dict) -> dict:
        """Commit exactly once. A request ID replay must have identical payload."""
        if not request_id or len(request_id) > 128:
            raise ProtocolError("request_id must be nonempty and <=128 characters")
        payload = _json(action)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            s = self._get(db, pid)
            prior = db.execute("SELECT participant_id,request_payload,response_payload "
                               "FROM synthetic_responses WHERE request_id=?",
                               (request_id,)).fetchone()
            if prior is not None:
                if prior[0] != pid or prior[1] != payload:
                    raise ProtocolError("request ID reused with different payload or participant")
                return json.loads(prior[2]) | {"replayed": True}
            if s["pending"] is None:
                raise ProtocolError("call next_action before acting")
            pending = s["pending"]
            kind = pending["action"]
            if kind == "COMPLETE":
                raise ProtocolError("session is complete")
            if kind == "QUESTION" or kind == "DROP_2":
                item = self.bank[pending["item_id"]]
                if action.get("item_id") != item.item_id:
                    raise ProtocolError("answer is not for the pending item")
                option_id = action.get("choice_id")
                if option_id not in [x[0] for x in item.options]:
                    raise ProtocolError("invalid option ID")
                correct = option_id == item.answer_id
                if s["stage"] in ("pretest", "practice"):
                    belief = Belief(s["mastery"].copy())
                    belief.observe(item.concept, correct)
                    s["mastery"] = belief.mastery
                if kind == "QUESTION":
                    if s["stage"] == "practice":
                        s["used"].append(item.item_id)
                    s["index"] += 1
                result = dict(accepted=True, stage=s["stage"], item_id=item.item_id)
                # Independent assessments must not disclose immediate correctness.
                if s["stage"] == "practice":
                    result["correct"] = correct
                self._event(db,pid,"answer_recorded",session=s["session"],
                            stage=s["stage"],item_id=item.item_id,correct=correct,
                            action_type=kind)
            elif kind == "FATIGUE":
                values = action.get("values")
                if (not isinstance(values,list) or len(values) != 6 or
                    any(type(v) is not int or not 1 <= v <= 5 for v in values)):
                    raise ProtocolError("fatigue questionnaire needs six integers in [1,5]")
                result = dict(accepted=True, stage="fatigue", count=6)
                self._event(db,pid,"fatigue_recorded",session=s["session"],values=values)
            elif kind in ("CONCEPT_SUMMARY","WORKED_EXAMPLE","SOCRATIC_HINT"):
                if action.get("acknowledged") is not True:
                    raise ProtocolError("resource requires acknowledged=true")
                result = dict(accepted=True, action=kind)
                self._event(db,pid,"synthetic_resource_acknowledged",session=s["session"],
                            action=kind, concept=pending["concept"])
            else:
                raise ProtocolError("unknown selected action")
            s["pending"] = None
            self._advance_stage(s)
            self._save(db,pid,s)
            db.execute("INSERT INTO synthetic_responses VALUES(?,?,?,?)",
                       (request_id,pid,payload,_json(result)))
            return result | {"replayed": False}

    def audit(self) -> dict:
        with self._connect() as db:
            statuses = db.execute("SELECT arm,stage,COUNT(*) FROM synthetic_participants "
                                  "GROUP BY arm,stage ORDER BY arm,stage").fetchall()
            events = db.execute("SELECT COUNT(*) FROM synthetic_protocol_events").fetchone()[0]
            requests = db.execute("SELECT COUNT(*) FROM synthetic_responses").fetchone()[0]
        return {"synthetic_only": True,"states":statuses,
                "event_count":events,"unique_request_count":requests,
                "bank_hash":self.bank_hash}
