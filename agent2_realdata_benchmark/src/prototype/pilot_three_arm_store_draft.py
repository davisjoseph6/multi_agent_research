"""DISCONNECTED three-arm behavioral-economics synthetic protocol rehearsal.

Uses the existing V3 A=POMCP, B=greedy, C=balanced-fixed selector, but has
NO API, real identity, institutional authorization, consent or recruitment.
Only generated SYN_PILOT_* records can use this module. All caller-provided
staff flags/timestamps are test fixtures, NOT genuine staff credentials.

No code in the production RCT candidate imports this module.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import uuid

from .pilot_item_bank_draft import PilotDraftItemBank
from .pilot_measurements_draft import MVAS_PROPOSED_VERSION
from .pilot_session_flow_draft import (
    PilotSequenceError, PilotSessionFlow, answer_question, fatigue_deltas,
    record_mvas, start_visit,
)
from .pilot_session_store_draft import (
    SyntheticPilotStore, _at, _json, _serialize,
)
from .rct_candidate_content import file_digest, read_csv
from .study_v2 import (
    BKT, Belief, CONCEPTS, RECOVERY_ACTIONS, RecoveryStatus,
)
from .study_v3_pomcp import EightConceptPOMCP
from .study_v3_runtime import SyntheticPOMCPProtocolEngine

POLICY_VERSION = "THREE_ARM_OFFLINE_SYNTHETIC_V1_NOT_AUTHORIZED"
ARMS = frozenset("ABC")
QUESTION_ACTIONS = ("QUESTION", "DROP_2")


class _OfflineV3Selector(SyntheticPOMCPProtocolEngine):
    """Use the original V3 decision method WITHOUT initializing its old DB.

    All attributes used by that method are explicitly initialized. This class
    is only a deterministic synthetic policy adapter, not a deployment engine.
    """
    def __init__(self, bank: PilotDraftItemBank, simulations: int):
        self.bank = bank.by_id
        self.planner = EightConceptPOMCP(simulations=simulations)
        self.max_resources_per_session = 2


class SyntheticThreeArmPilotStore(SyntheticPilotStore):
    """Separate, unapproved prototype; never put real data in its database."""

    def __init__(self, path: str | Path, *,
                 items_path: str | Path, resources_path: str | Path,
                 simulations: int = 240):
        self.policy_bank = PilotDraftItemBank(items_path)
        resource_rows = read_csv(resources_path)
        if len(resource_rows) != 32 or len({
            (r["concept"], r["action"]) for r in resource_rows
        }) != 32:
            raise ValueError("expected 32 unique draft resources")
        self.resources = {
            (r["concept"], r["action"]): dict(
                resource_id=r["resource_id"],
                text=r["resource_text"],
                source=r.get("source_citation", ""),
                version_sha256=sha256(_json(r).encode()).hexdigest(),
            )
            for r in resource_rows
        }
        if set(self.resources) != {
            (concept, action)
            for concept in CONCEPTS for action in RECOVERY_ACTIONS
        }:
            raise ValueError("resource bank concept/action coverage is incomplete")
        if type(simulations) is not int or not 41 <= simulations <= 100000:
            raise ValueError("V3 simulations must be in 41..100000")
        self.selector = _OfflineV3Selector(self.policy_bank, simulations)
        self.policy_config = _json(dict(
            version=POLICY_VERSION,
            item_sha256=self.policy_bank.sha256,
            resource_sha256=file_digest(resources_path),
            simulation_count=simulations,
            model_sha256=self.selector.planner.assumptions.fingerprint,
            selector_source_sha256=file_digest(
                Path(__file__).with_name("study_v3_runtime.py")),
            policy_source_sha256=file_digest(Path(__file__)),
            control="greedy",
            resource_budget_each_session=2,
            practice_counts=[20, 20, 15],
            mvas_version=MVAS_PROPOSED_VERSION,
        ))
        super().__init__(path, items_path=items_path)
        with self._transaction() as db:
            # Deliberately cannot add 3-arm behavior to an old populated bank
            # database. A separate policy-metadata lock prevents config drift.
            prior = {
                row["name"] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "pilot_three_arm_config" not in prior:
                count = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
                if count:
                    raise PilotSequenceError(
                        "cannot convert a populated count-only/bank-only database")
            db.execute("""CREATE TABLE IF NOT EXISTS pilot_three_arm_config (
                id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS pilot_three_arm_people (
                pid TEXT PRIMARY KEY REFERENCES pilot_people(pid),
                arm TEXT NOT NULL CHECK(arm IN ('A','B','C')),
                policy TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS pilot_three_arm_selected (
                action_id TEXT PRIMARY KEY REFERENCES pilot_actions(action_id),
                selected TEXT NOT NULL)""")
            row = db.execute(
                "SELECT config FROM pilot_three_arm_config WHERE id=1"
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO pilot_three_arm_config(id,config) VALUES(1,?)",
                    (self.policy_config,))
            elif row["config"] != self.policy_config:
                raise PilotSequenceError("policy or source fingerprint mismatch")

    @staticmethod
    def _policy(db, pid: str) -> dict:
        row = db.execute(
            "SELECT policy FROM pilot_three_arm_people WHERE pid=?",
            (pid,)
        ).fetchone()
        if row is None:
            raise PilotSequenceError("record lacks an offline three-arm assignment")
        return json.loads(row["policy"])

    @staticmethod
    def _save_policy(db, pid: str, value: dict) -> None:
        db.execute(
            "UPDATE pilot_three_arm_people SET policy=? WHERE pid=?",
            (_json(value), pid)
        )

    def new_synthetic_participant(self, *, arm: str,
                                  at: datetime | None = None) -> str:
        if type(arm) is not str or arm not in ARMS:
            raise PilotSequenceError("A, B or C synthetic assignment required")
        timestamp = _at(at)
        pid = "SYN_PILOT_" + uuid.uuid4().hex
        policy = dict(
            arm=arm, mastery={c: 0.2 for c in CONCEPTS},
            used=[], recovery=asdict(RecoveryStatus()),
        )
        with self._transaction() as db:
            db.execute(
                "INSERT INTO pilot_people(pid,state,created_at) VALUES(?,?,?)",
                (pid, _serialize(PilotSessionFlow()), timestamp.isoformat())
            )
            db.execute(
                "INSERT INTO pilot_three_arm_people(pid,arm,policy) VALUES(?,?,?)",
                (pid, arm, _json(policy))
            )
            self._event(db, pid, timestamp, "synthetic_three_arm_record_created",
                        assigned_arm=arm)
        return pid

    def start_supervised_visit(
        self, pid: str, *, visit: int, at: datetime | None = None,
        offline_staff_authorized: bool = False,
        synthetic_release_authorized: bool = False,
    ) -> dict:
        timestamp = _at(at)
        with self._transaction() as db:
            state = self._load(db, pid)
            policy = self._policy(db, pid)
            updated = start_visit(
                state, visit=visit, at=timestamp,
                staff_authorized=offline_staff_authorized,
                release_authorized=synthetic_release_authorized,
            )
            # Reset ONLY visit-specific recovery budget. Mastery and 55-item
            # no-repeat history persist over all three visits.
            policy["recovery"] = asdict(RecoveryStatus())
            self._save(db, pid, updated)
            self._save_policy(db, pid, policy)
            self._event(db, pid, timestamp, "synthetic_visit_started",
                        visit=visit, assigned_arm=policy["arm"])
        return dict(accepted=True, stage=updated.stage, visit=visit)

    def next_action(self, pid: str, *, at: datetime | None = None) -> dict:
        timestamp = _at(at)
        with self._transaction() as db:
            state = self._load(db, pid)
            policy = self._policy(db, pid)
            if state.last_event_at is not None and timestamp < state.last_event_at:
                raise PilotSequenceError("action offered before previous event")
            if state.stage == "awaiting_visit":
                return dict(action="AWAITING_SUPERVISOR", visit=state.session + 1)
            if state.stage == "complete":
                return dict(action="COMPLETE")
            if state.stage not in ("pretest", "practice", "posttest",
                                   "mvas_pre", "mvas_post"):
                raise PilotSequenceError("unexpected stage")
            pending = db.execute(
                "SELECT public FROM pilot_actions WHERE pid=? "
                "AND completed_at IS NULL", (pid,)
            ).fetchall()
            if len(pending) > 1:
                raise PilotSequenceError("multiple incomplete actions")
            if pending:
                return json.loads(pending[0]["public"])

            if state.stage in ("mvas_pre", "mvas_post"):
                selected = dict(action="MVAS")
            elif state.stage == "practice":
                selector_state = dict(
                    policy, stage="practice", session=state.session,
                    index=state.index,
                )
                # V3 selects A planner+recovery, B greedy, C fixed.
                # The planner can update the recovery-spent counter.
                selected = self.selector._candidate(selector_state)
                policy["recovery"] = selector_state["recovery"]
            else:
                item = self.policy_bank.select(state)
                selected = dict(
                    action="QUESTION", item_id=item.item_id,
                    concept=item.concept
                )

            kind = selected["action"]
            if kind != "MVAS" and kind not in QUESTION_ACTIONS \
                    and kind not in RECOVERY_ACTIONS:
                raise PilotSequenceError("unknown selected policy action")
            action_id = uuid.uuid4().hex
            public = dict(
                action_id=action_id, action=kind, stage=state.stage,
                session=state.session, index=state.index,
                synthetic_only=True,
            )
            if kind == "MVAS":
                public["instrument_proposed_version"] = MVAS_PROPOSED_VERSION
                public["scale"] = dict(minimum=0, maximum=100, step=1)
            if kind in QUESTION_ACTIONS:
                item = self.policy_bank.by_id.get(selected["item_id"])
                if item is None:
                    raise PilotSequenceError("selector returned missing item")
                required_form = (
                    "recovery_drop2" if kind == "DROP_2" else state.stage
                )
                if item.form != required_form:
                    raise PilotSequenceError("selector returned incorrect item form")
                if kind == "QUESTION" and state.stage == "practice" \
                        and item.item_id in policy["used"]:
                    raise PilotSequenceError("practice item already used")
                public["question"] = item.public()
            if kind in RECOVERY_ACTIONS:
                public["resource"] = self.resources[(selected["concept"], kind)]
            public["draft_content_not_approved"] = True
            public_json = _json(public)
            db.execute(
                "INSERT INTO pilot_actions VALUES(?,?,?,?,NULL,NULL,NULL)",
                (action_id, pid, public_json, timestamp.isoformat()),
            )
            db.execute(
                "INSERT INTO pilot_three_arm_selected(action_id,selected) "
                "VALUES(?,?)", (action_id, _json(selected))
            )
            self._save_policy(db, pid, policy)
            self._event(db, pid, timestamp, "synthetic_action_offered",
                        action_id=action_id, assigned_arm=policy["arm"],
                        action_kind=kind, stage=state.stage)
            return json.loads(public_json)

    def submit(
        self, pid: str, action_id: str, request_id: str, response: dict,
        *, at: datetime | None = None,
    ) -> dict:
        timestamp = _at(at)
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise PilotSequenceError("valid request ID required")
        if not isinstance(action_id, str) or len(action_id) != 32 \
                or type(response) is not dict:
            raise PilotSequenceError("valid action and response object required")
        payload = _json(dict(action_id=action_id, response=response))
        with self._transaction() as db:
            state = self._load(db, pid)
            policy = self._policy(db, pid)
            prior = db.execute(
                "SELECT payload,result FROM pilot_requests "
                "WHERE pid=? AND request_id=?", (pid, request_id)
            ).fetchone()
            if prior is not None:
                if prior["payload"] != payload:
                    raise PilotSequenceError("request ID reused with different content")
                return {**json.loads(prior["result"]), "replayed": True}
            row = db.execute(
                "SELECT a.public,a.rendered_at,a.completed_at,s.selected "
                "FROM pilot_actions a JOIN pilot_three_arm_selected s "
                "ON s.action_id=a.action_id "
                "WHERE a.pid=? AND a.action_id=?",
                (pid, action_id)
            ).fetchone()
            if row is None or row["completed_at"] is not None:
                raise PilotSequenceError("foreign, stale or completed action")
            if row["rendered_at"] is None:
                raise PilotSequenceError("render acknowledgement required")
            if timestamp < datetime.fromisoformat(row["rendered_at"]):
                raise PilotSequenceError("answer timestamp precedes render")
            public, selected = json.loads(row["public"]), json.loads(row["selected"])
            if (public["stage"], public["session"], public["index"]) != (
                state.stage, state.session, state.index
            ):
                raise PilotSequenceError("pending action does not match state")
            kind = selected["action"]
            recorded = response
            extra = {}
            if kind in QUESTION_ACTIONS:
                if set(response) != {"choice_id"} or type(response["choice_id"]) is not str:
                    raise PilotSequenceError("one choice_id required")
                item = self.policy_bank.by_id[selected["item_id"]]
                if response["choice_id"] not in {k for k, _ in item.options}:
                    raise PilotSequenceError("option not valid for selected question")
                if public.get("question", {}).get("item_id") != item.item_id:
                    raise PilotSequenceError("public/private item mismatch")
                correct = response["choice_id"] == item.answer_id
                recorded = dict(
                    choice_id=response["choice_id"], item_id=item.item_id,
                    correct=correct,
                )
                if state.stage == "pretest":
                    policy["mastery"][item.concept] = BKT().posterior(
                        policy["mastery"][item.concept], correct
                    )
                elif state.stage == "practice":
                    belief = Belief(policy["mastery"].copy())
                    belief.observe(item.concept, correct)
                    policy["mastery"] = belief.mastery
                    extra["correct"] = correct
                if kind == "QUESTION":
                    if state.stage == "practice":
                        if item.item_id in policy["used"]:
                            raise PilotSequenceError("repeated practice item")
                        policy["used"].append(item.item_id)
                    updated = answer_question(state, at=timestamp)
                else:
                    # DROP_2 is a recovery action, not a 56th practice question.
                    updated = replace(state, last_event_at=timestamp)
            elif kind in RECOVERY_ACTIONS:
                if set(response) != {"status"} or response["status"] not in (
                    "completed", "skipped"
                ):
                    raise PilotSequenceError("explicit completed/skipped status required")
                updated = replace(state, last_event_at=timestamp)
            elif kind == "MVAS":
                if set(response) != {"rating"}:
                    raise PilotSequenceError("one 0..100 M-VAS response required")
                updated = record_mvas(state, at=timestamp, rating=response["rating"])
            else:
                raise PilotSequenceError("unknown response type")
            db.execute(
                "UPDATE pilot_actions SET completed_at=?,response=? "
                "WHERE action_id=?", (timestamp.isoformat(), _json(recorded), action_id)
            )
            self._save(db, pid, updated)
            self._save_policy(db, pid, policy)
            result = dict(accepted=True, stage=updated.stage,
                          session=updated.session, **extra)
            db.execute(
                "INSERT INTO pilot_requests VALUES(?,?,?,?)",
                (pid, request_id, payload, _json(result))
            )
            self._event(db, pid, timestamp, "synthetic_action_completed",
                        action_id=action_id, action_kind=kind,
                        assigned_arm=policy["arm"])
        return {**result, "replayed": False}

    def snapshot(self, pid: str) -> dict:
        base = super().snapshot(pid)
        with self._transaction() as db:
            policy = self._policy(db, pid)
            rows = db.execute(
                "SELECT a.public,a.completed_at FROM pilot_actions a "
                "WHERE a.pid=?", (pid,)
            ).fetchall()
        recovery = [
            row for row in rows if json.loads(row["public"])["action"]
            in RECOVERY_ACTIONS
        ]
        return dict(
            base, arm=policy["arm"],
            unique_practice_used=len(policy["used"]),
            recovery_offered=len(recovery),
            recovery_completed=sum(r["completed_at"] is not None for r in recovery),
            pilot_policy_version=POLICY_VERSION,
        )

    def audit_arms(self) -> dict:
        with self._transaction() as db:
            assigned = dict(db.execute(
                "SELECT arm,COUNT(*) FROM pilot_three_arm_people GROUP BY arm"
            ).fetchall())
            rows = db.execute(
                "SELECT p.arm,a.public,a.completed_at FROM pilot_actions a "
                "JOIN pilot_three_arm_people p ON p.pid=a.pid"
            ).fetchall()
        delivered = Counter()
        for row in rows:
            action = json.loads(row["public"])
            if row["completed_at"] is not None:
                delivered[(row["arm"],action["action"])] += 1
        return dict(
            synthetic_only=True, approved_for_humans=False,
            allocated=assigned,
            completed_actions_by_arm={
                arm: {kind: n for (a, kind), n in delivered.items() if a == arm}
                for arm in "ABC"
            }
        )
