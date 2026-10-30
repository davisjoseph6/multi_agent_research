"""Isolated, policy-locked synthetic protocol for the opt-in V5 guarded planner.

This is NOT a human-subject study implementation. Uses fictional SYN_ IDs only.
The original V3 classes are intentionally unchanged.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sqlite3

from .study_v2_runtime import ProtocolError
from .study_v3_runtime import SyntheticPOMCPProtocolEngine
from .study_v5_guarded_planner import BeliefSupportGuardedPOMCP


POLICY_ID = BeliefSupportGuardedPOMCP.policy_id


def _source_fingerprint() -> str:
    """Bind the synthetic dataset to the implemented policy and runtime source."""
    from .study_v3_pomcp import EightConceptPOMCP
    relevant = (
        BeliefSupportGuardedPOMCP,
        EightConceptPOMCP,
        SyntheticPOMCPProtocolEngine,
        PolicyLockedGuardedProtocolEngine,
    )
    h = sha256()
    for klass in relevant:
        path = Path(inspect.getfile(klass))
        h.update(path.name.encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
    return h.hexdigest()


class PolicyLockedGuardedProtocolEngine(SyntheticPOMCPProtocolEngine):
    """Synthetic V5 intervention; rejects silent V3->V5 database conversion.

    V5 records complete planning traces within action_selected events so
    decisions remain auditable after pending actions are cleared.
    Note: the legacy V3 class itself cannot be forced to reject a V5 DB;
    use an isolated DB and only the V5 class for a V5 run.
    """

    def __init__(self, path, bank, *, planner=None, max_resources_per_session=2):
        if planner is None:
            planner = BeliefSupportGuardedPOMCP()
        if type(planner) is not BeliefSupportGuardedPOMCP:
            raise TypeError("V5 requires the exact guarded planner class")
        self.v5_policy_id = POLICY_ID
        path = Path(path)
        if path.exists():
            # Read-only preflight: a v3-only dataset must never be upgraded.
            db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
            try:
                tables = {
                    row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "synthetic_v3_config" in tables and "synthetic_v5_policy_lock" not in tables:
                    raise ProtocolError("refuse to convert preexisting V3 database into V5")
            finally:
                db.close()
        super().__init__(
            path, bank, planner=planner,
            max_resources_per_session=max_resources_per_session,
        )
        config = {
            "policy_id": POLICY_ID,
            "source_sha256": _source_fingerprint(),
            "assumption_hash": planner.assumptions.fingerprint,
            "simulations": planner.simulations,
            "horizon": planner.horizon,
            "exploration": planner.exploration,
            "discount": planner.discount,
            "max_resources_per_session": max_resources_per_session,
            "item_bank_hash": self.bank_hash,
            "synthetic_only": True,
        }
        encoded = json.dumps(config, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                CREATE TABLE IF NOT EXISTS synthetic_v5_policy_lock (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    configuration_json TEXT NOT NULL
                )
            """)
            prior = db.execute(
                "SELECT configuration_json FROM synthetic_v5_policy_lock WHERE id=1"
            ).fetchone()
            if prior is None:
                existing = db.execute(
                    "SELECT count(*) FROM synthetic_participants"
                ).fetchone()[0]
                if existing:
                    raise ProtocolError("refuse V5 activation with prior participants")
                db.execute(
                    "INSERT INTO synthetic_v5_policy_lock VALUES (1, ?)",
                    (encoded,),
                )
            elif prior[0] != encoded:
                raise ProtocolError("V5 policy/configuration/source changed")
        self.v5_config = config

    def next_action(self, participant_id):
        """Create pending action and full immutable planning event atomically."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            s = self._get(db, participant_id)
            if s["pending"] is None:
                s["pending"] = self._candidate(s)
                pending = s["pending"]
                provenance = pending.get("planning_trace")
                if s["arm"] == "A" and s["stage"] == "practice" and s["index"] > 0:
                    if not isinstance(provenance, dict):
                        raise ProtocolError("missing guarded planning trace")
                    if provenance.get("policy_id") != POLICY_ID:
                        raise ProtocolError("wrong policy trace")
                self._event(
                    db, participant_id, "action_selected",
                    stage=s["stage"], session=s["session"],
                    action=pending["action"], item_id=pending.get("item_id"),
                    bank_hash=self.bank_hash, policy_id=POLICY_ID,
                    planning_trace=provenance,
                )
                self._save(db, participant_id, s)
            selected = dict(s["pending"])
            if selected.get("item_id") is not None:
                selected["question"] = self.bank[selected["item_id"]].public()
            return selected

    def guarded_decision_audit(self) -> dict:
        """Read-only audit of the durable V5 action-selection record."""
        with self._connect() as db:
            encoded = db.execute(
                "SELECT configuration_json FROM synthetic_v5_policy_lock WHERE id=1"
            ).fetchone()
            if encoded is None or json.loads(encoded[0]) != self.v5_config:
                raise ProtocolError("V5 configuration mismatch")
            rows = db.execute(
                "SELECT event_json FROM synthetic_protocol_events ORDER BY seq"
            ).fetchall()
        decisions = [json.loads(row[0]) for row in rows]
        selected = [d for d in decisions if d["type"] == "action_selected"]
        if any(d.get("policy_id") != POLICY_ID for d in selected):
            raise ProtocolError("mixed policy identity in action log")
        plans = [d["planning_trace"] for d in selected if d.get("planning_trace")]
        if any(p.get("policy_id") != POLICY_ID for p in plans):
            raise ProtocolError("mixed planning trace identity")
        return {
            "synthetic_only": True,
            "policy_id": POLICY_ID,
            "policy_source_sha256": self.v5_config["source_sha256"],
            "action_events": len(selected),
            "planner_decisions": len(plans),
            "guard_interventions": sum(bool(p["guard_applied"]) for p in plans),
            "raw_action_preserved": all(
                bool(p.get("raw_action")) and bool(p.get("raw_concept"))
                for p in plans
            ),
        }
