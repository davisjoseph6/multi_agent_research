"""Transactional RCT release candidate; default use is fictional rehearsal.

The V3 selector is reused, not scientifically validated by this integration.
No simulator latent state is supplied to the online selector.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

from .rct_candidate_content import canonical, digest, release_report
from .study_v2 import BKT, Belief, CONCEPTS, RECOVERY_ACTIONS, RecoveryStatus
from .study_v2_runtime import ProtocolError
from .study_v3_runtime import SyntheticPOMCPProtocolEngine
from .study_v3_pomcp import EightConceptPOMCP


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def policy_record(simulations=240, control="greedy", *, deployment=None):
    if type(simulations) is not int or not 41 <= simulations <= 100000:
        raise ValueError("use at least 41 simulations for the 40-action root")
    if control not in ("greedy", "pomcp_no_recovery"):
        raise ValueError("unknown control policy")
    planner = EightConceptPOMCP(simulations=simulations)
    return dict(version="rct_candidate_v1", arm_A="V3_POMCP",
                arm_B=control, arm_C="balanced_fixed_v3", simulations=simulations,
                horizon=planner.horizon, exploration=planner.exploration,
                discount=planner.discount, assumptions=asdict(planner.assumptions),
                resources_per_session=2, practice_counts=[20, 20, 15],
                recovery_counts_toward_practice=False,
                allocation="private_random_permuted_blocks_6_or_9_equal_ABC",
                primary_measure="independently_scored_posttest_16_items",
                dose="55_practice_plus_up_to_6_resources_no_equal_time_claim",
                belief_update="historical_v3_BKT_pretest_posterior_only",
                resource_skip="informational_allowed_DROP2_requires_answer",
                create_measurement="MCQ_recognition_only_not_creation",
                deployment=deployment or {"allowed_hosts": ["127.0.0.1", "localhost", "::1"],
                                          "behind_one_local_tls_proxy": False})


class RCTCandidateEngine(SyntheticPOMCPProtocolEngine):
    """Separate schema; historical synthetic databases are never upgraded.

Only the parent's in-memory action selector and stage transitions are reused.
Authentication, allocation, delivery, responses and audit writes below share
one transaction. A completed submission cannot be applied to a later action.
"""
    def __init__(self, database, bundle, *, simulations=240, control="greedy",
                 mode="rehearsal", release_path=None, deployment=None):
        if mode not in ("rehearsal", "live"):
            raise ValueError("mode must be rehearsal or live")
        self.bundle = bundle
        self.policy = policy_record(simulations, control, deployment=deployment)
        self.release = release_report(bundle, self.policy, release_path)
        if mode == "live" and not self.release["mechanical_gate_passed"]:
            raise ProtocolError("Live enrollment blocked: " + "; ".join(self.release["blockers"]))
        self.mode = mode
        self.path = Path(database)
        self.bank = {q.item_id: q for q in bundle.items}
        self.bank_hash = bundle.fingerprint
        self.planner = EightConceptPOMCP(simulations=simulations)
        self.max_resources_per_session = 2
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.configuration = dict(mode=mode, candidate=self.release["candidate_sha256"])
        with self._transaction() as db:
            old = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if old and "rct_config" not in old:
                raise ProtocolError("use a fresh candidate database, not an existing study database")
            for statement in (
                "CREATE TABLE IF NOT EXISTS rct_config (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS rct_people (pid TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, expires REAL NOT NULL, status TEXT NOT NULL, state TEXT, consent_at TEXT, consent_version TEXT)",
                "CREATE TABLE IF NOT EXISTS rct_allocation (seq INTEGER PRIMARY KEY AUTOINCREMENT, arm TEXT NOT NULL, pid TEXT UNIQUE, block INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS rct_actions (id TEXT PRIMARY KEY, pid TEXT NOT NULL REFERENCES rct_people(pid), selected TEXT NOT NULL, public TEXT NOT NULL, offered_at TEXT NOT NULL, rendered_at TEXT, completed_at TEXT, response TEXT)",
                "CREATE TABLE IF NOT EXISTS rct_requests (pid TEXT NOT NULL REFERENCES rct_people(pid), request_id TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(pid,request_id))",
                "CREATE TABLE IF NOT EXISTS rct_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, pid TEXT NOT NULL REFERENCES rct_people(pid), at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)",
            ):
                db.execute(statement)
            prior = db.execute("SELECT value FROM rct_config WHERE id=1").fetchone()
            if prior is None:
                db.execute("INSERT INTO rct_config VALUES(1,?)", (canonical(self.configuration),))
            elif prior[0] != canonical(self.configuration):
                raise ProtocolError("candidate code, content, policy or mode changed; use a new database")
        self.path.chmod(0o600)

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
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

    def _event(self, db, pid, kind, **data):
        db.execute("INSERT INTO rct_events(pid,at,kind,payload) VALUES(?,?,?,?)",
                   (pid, stamp(), kind, canonical(data)))

    def issue_invitation(self, *, lifetime_hours=72):
        if type(lifetime_hours) not in (int, float) or not 0 < lifetime_hours <= 8760:
            raise ValueError("invitation lifetime must be in (0,8760] hours")
        token = secrets.token_urlsafe(32)
        pid = ("SYN_" if self.mode == "rehearsal" else "P_") + uuid.uuid4().hex
        with self._transaction() as db:
            db.execute("INSERT INTO rct_people VALUES(?,?,?,'invited',NULL,NULL,NULL)",
                       (pid, sha256(token.encode()).hexdigest(), time.time() + lifetime_hours * 3600))
            self._event(db, pid, "invitation_issued", mode=self.mode)
        return dict(participant_id=pid, invitation=token, mode=self.mode)

    def rotate_invitation(self, pid, *, lifetime_hours=72):
        """Staff-only recovery after independent identity verification; keep assignment."""
        if not isinstance(pid, str) or type(lifetime_hours) not in (int, float) or not 0 < lifetime_hours <= 8760:
            raise ValueError("valid record and invitation lifetime required")
        token = secrets.token_urlsafe(32)
        with self._transaction() as db:
            row = db.execute("SELECT status FROM rct_people WHERE pid=?", (pid,)).fetchone()
            if row is None or row["status"] == "withdrawn":
                raise ProtocolError("unknown or stopped participation")
            db.execute("UPDATE rct_people SET token_hash=?,expires=? WHERE pid=?",
                       (sha256(token.encode()).hexdigest(), time.time() + lifetime_hours * 3600, pid))
            self._event(db, pid, "invitation_rotated")
        return dict(participant_id=pid, invitation=token, mode=self.mode)

    @staticmethod
    def _person(db, token, *, allow_invited=False, allow_withdrawn=False):
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise ProtocolError("invalid or expired invitation")
        row = db.execute("SELECT * FROM rct_people WHERE token_hash=?",
                         (sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None or row["expires"] < time.time():
            raise ProtocolError("invalid or expired invitation")
        if row["status"] == "withdrawn" and not allow_withdrawn:
            raise ProtocolError("participation has stopped")
        if row["status"] == "invited" and not allow_invited:
            raise ProtocolError("participation agreement required")
        return row

    def information(self, token):
        with self._transaction() as db:
            person = self._person(db, token, allow_invited=True, allow_withdrawn=True)
        return dict(mode=self.mode, information=self.bundle.information,
                    information_version=self.bundle.hashes["information"],
                    status=person["status"])

    @staticmethod
    def _allocate(db, pid):
        slot = db.execute("SELECT seq,arm FROM rct_allocation WHERE pid IS NULL ORDER BY seq LIMIT 1").fetchone()
        if slot is None:
            rng = secrets.SystemRandom()
            arms = list("ABC") * rng.choice((2, 3))
            rng.shuffle(arms)
            block = db.execute("SELECT COALESCE(MAX(block),0)+1 FROM rct_allocation").fetchone()[0]
            db.executemany("INSERT INTO rct_allocation(arm,block) VALUES(?,?)", [(a, block) for a in arms])
            slot = db.execute("SELECT seq,arm FROM rct_allocation WHERE pid IS NULL ORDER BY seq LIMIT 1").fetchone()
        db.execute("UPDATE rct_allocation SET pid=? WHERE seq=?", (pid, slot["seq"]))
        return slot["arm"]

    def enroll(self, token, *, agreed, information_version):
        if agreed is not True or information_version != self.bundle.hashes["information"]:
            raise ProtocolError("agreement to this information version is required")
        with self._transaction() as db:
            person = self._person(db, token, allow_invited=True)
            if person["status"] != "invited":
                return dict(accepted=True, created=False)
            arm = self._allocate(db, person["pid"])
            state = dict(arm=arm, stage="pretest", session=0, index=0,
                         mastery={c: .2 for c in CONCEPTS}, used=[],
                         recovery=asdict(RecoveryStatus()), pending=None)
            db.execute("UPDATE rct_people SET status='active',state=?,consent_at=?,consent_version=? WHERE pid=?",
                       (canonical(state), stamp(), information_version, person["pid"]))
            self._event(db, person["pid"], "enrolled", arm=arm, information_version=information_version,
                        candidate_sha256=self.release["candidate_sha256"])
        return dict(accepted=True, created=True)

    def _candidate(self, state):
        if state["arm"] == "B" and self.policy["arm_B"] == "pomcp_no_recovery" and state["stage"] == "practice":
            temporary = {**state, "arm": "A", "recovery": {**state["recovery"], "pomcp_resource_spent": 2}}
            action = super()._candidate(temporary)
            action["control_variant"] = "matched_POMCP_recovery_disabled"
            return action
        return super()._candidate(state)

    def _public(self, selected, state, action_id):
        public = dict(action_id=action_id, action=selected["action"], stage=state["stage"],
                      session=state["session"], index=state["index"], mode=self.mode)
        if selected.get("item_id"):
            public["question"] = self.bank[selected["item_id"]].public()
        if selected["action"] in RECOVERY_ACTIONS:
            public["resource"] = self.bundle.resources[selected["concept"], selected["action"]]
        if selected["action"] == "FATIGUE":
            public["questionnaire"] = {key: self.bundle.fatigue[key] for key in ("version", "items", "labels")}
        return json.loads(canonical(public))

    def next_action(self, token):
        with self._transaction() as db:
            person = self._person(db, token)
            state = json.loads(person["state"])
            if state["stage"] == "complete":
                return dict(action="COMPLETE", mode=self.mode)
            if state["pending"]:
                row = db.execute("SELECT public FROM rct_actions WHERE id=? AND pid=?",
                                 (state["pending"], person["pid"])).fetchone()
                return json.loads(row[0])
            selected = self._candidate(state)
            action_id = uuid.uuid4().hex
            public = self._public(selected, state, action_id)
            db.execute("INSERT INTO rct_actions VALUES(?,?,?,?,?,NULL,NULL,NULL)",
                       (action_id, person["pid"], canonical(selected), canonical(public), stamp()))
            state["pending"] = action_id
            db.execute("UPDATE rct_people SET state=? WHERE pid=?", (canonical(state), person["pid"]))
            self._event(db, person["pid"], "action_offered", action_id=action_id,
                        action=selected["action"], stage=state["stage"], session=state["session"],
                        resource_version=public.get("resource", {}).get("version_sha256"))
            return public

    def rendered(self, token, action_id):
        with self._transaction() as db:
            person = self._person(db, token)
            state = json.loads(person["state"])
            if not isinstance(action_id, str) or state["pending"] != action_id:
                raise ProtocolError("render event is not for the current action")
            changed = db.execute("UPDATE rct_actions SET rendered_at=? WHERE id=? AND pid=? AND rendered_at IS NULL",
                                 (stamp(), action_id, person["pid"])).rowcount
            if changed:
                self._event(db, person["pid"], "client_reported_render", action_id=action_id)
        return dict(accepted=True)

    def act(self, token, request_id, action_id, response):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or not isinstance(response, dict):
            raise ProtocolError("request ID and response object required")
        if not isinstance(action_id, str) or len(action_id) != 32:
            raise ProtocolError("valid action ID required")
        payload = canonical(dict(action_id=action_id, response=response))
        with self._transaction() as db:
            person = self._person(db, token)
            prior = db.execute("SELECT payload,result FROM rct_requests WHERE pid=? AND request_id=?",
                               (person["pid"], request_id)).fetchone()
            if prior:
                if prior["payload"] != payload:
                    raise ProtocolError("request ID reused with different content")
                return {**json.loads(prior["result"]), "replayed": True}
            state = json.loads(person["state"])
            if state["pending"] != action_id:
                raise ProtocolError("stale or foreign action")
            row = db.execute("SELECT * FROM rct_actions WHERE id=? AND pid=?", (action_id, person["pid"])).fetchone()
            if row["rendered_at"] is None:
                raise ProtocolError("render acknowledgment required before response")
            selected = json.loads(row["selected"])
            kind = selected["action"]
            result = dict(accepted=True)
            record = dict(response=response, stage=state["stage"], session=state["session"], action=kind)
            if kind in ("QUESTION", "DROP_2"):
                item = self.bank[selected["item_id"]]
                if (set(response) != {"choice_id"} or not isinstance(response["choice_id"], str)
                        or response["choice_id"] not in dict(item.options)):
                    raise ProtocolError("one valid choice_id required")
                correct = response["choice_id"] == item.answer_id
                record.update(item_id=item.item_id, correct=correct)
                if state["stage"] == "pretest":
                    state["mastery"][item.concept] = BKT().posterior(state["mastery"][item.concept], correct)
                elif state["stage"] == "practice":
                    belief = Belief(state["mastery"].copy())
                    belief.observe(item.concept, correct)
                    state["mastery"] = belief.mastery
                    result["correct"] = correct
                if kind == "QUESTION":
                    if state["stage"] == "practice":
                        state["used"].append(item.item_id)
                    state["index"] += 1
            elif kind == "FATIGUE":
                values = response.get("values")
                if (set(response) != {"values"} or not isinstance(values, list) or len(values) != 6 or
                        any(type(v) is not int or not 1 <= v <= 5 for v in values)):
                    raise ProtocolError("six integers from 1 to 5 required")
            elif kind in RECOVERY_ACTIONS:
                if set(response) != {"status"} or response["status"] not in ("completed", "skipped"):
                    raise ProtocolError("resource status must be completed or skipped")
            else:
                raise ProtocolError("unexpected action")
            # Selected, rendered and completion/skip remain distinct evidence.
            db.execute("UPDATE rct_actions SET completed_at=?,response=? WHERE id=?",
                       (stamp(), canonical(record), action_id))
            self._event(db, person["pid"], "response_recorded", action_id=action_id, **record)
            state["pending"] = None
            self._advance_stage(state)
            status = "complete" if state["stage"] == "complete" else "active"
            db.execute("UPDATE rct_people SET state=?,status=? WHERE pid=?", (canonical(state), status, person["pid"]))
            db.execute("INSERT INTO rct_requests VALUES(?,?,?,?)", (person["pid"], request_id, payload, canonical(result)))
        return {**result, "replayed": False}

    def withdraw(self, token):
        with self._transaction() as db:
            person = self._person(db, token, allow_invited=True, allow_withdrawn=True)
            if person["status"] != "withdrawn":
                db.execute("UPDATE rct_people SET status='withdrawn' WHERE pid=?", (person["pid"],))
                self._event(db, person["pid"], "participation_stopped")
        return dict(stopped=True, message="Participation stopped. Contact the study team for data-rights requests described in the information sheet.")

    def audit(self):
        with self._transaction() as db:
            counts = {row["status"]: row["n"] for row in db.execute("SELECT status,COUNT(*) n FROM rct_people GROUP BY status")}
            resource = list(db.execute("SELECT public,rendered_at,completed_at,response FROM rct_actions"))
            pending = db.execute("SELECT COUNT(*) FROM rct_actions WHERE completed_at IS NULL").fetchone()[0]
            events = db.execute("SELECT COUNT(*) FROM rct_events").fetchone()[0]
        recoveries = [r for r in resource if "resource" in json.loads(r["public"])]
        return dict(mode=self.mode, candidate_sha256=self.release["candidate_sha256"],
                    people=counts, actions=len(resource), pending_actions=pending, events=events,
                    resources_offered=len(recoveries),
                    resources_render_reported=sum(r["rendered_at"] is not None for r in recoveries),
                    resources_responded=sum(r["completed_at"] is not None for r in recoveries),
                    enrollment_blockers=self.release["blockers"], human_efficacy_established=False)

    def export_private(self):
        """Operator-only. Pseudonymous rows remain personal data in a live trial."""
        with self._transaction() as db:
            people = [dict(r) for r in db.execute("SELECT pid,status,state,consent_at,consent_version FROM rct_people")]
            actions = [dict(r) for r in db.execute("SELECT * FROM rct_actions ORDER BY offered_at,id")]
            events = [dict(r) for r in db.execute("SELECT * FROM rct_events ORDER BY seq")]
        outcomes = []
        for p in people:
            if not p["state"]:
                continue
            s = json.loads(p["state"])
            completed = [json.loads(a["response"]) for a in actions if a["pid"] == p["pid"] and a["response"]]
            out = dict(pid=p["pid"], assigned_arm=s["arm"], status=p["status"])
            for form in ("pretest", "posttest"):
                answers = [a for a in completed if a["stage"] == form]
                out[form + "_answered"] = len(answers)
                out[form + "_score"] = sum(a["correct"] for a in answers) if len(answers) == 16 else None
            outcomes.append(out)
        return dict(mode=self.mode, candidate=self.configuration, policy=self.policy,
                    outcomes=outcomes, people=people, actions=actions, events=events,
                    note="Incomplete outcomes are null, not zero. Includes all assigned participants; not a fitted causal analysis.")

    def backup(self, destination):
        target = Path(destination)
        if target.exists():
            raise FileExistsError("backup target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        # SQLite's backup API includes committed state even when journal modes change.
        with sqlite3.connect(self.path) as source, sqlite3.connect(target) as copy:
            source.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ProtocolError("backup integrity check failed")
        target.chmod(0o600)
        return dict(backup_sha256=sha256(target.read_bytes()).hexdigest())
