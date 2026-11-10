"""Single-file transactional synthetic admission + three-arm learning prototype.

This module is deliberately OFFLINE and DISCONNECTED from both Flask apps.
It cannot accept real identities, authenticate personnel, approve a protocol,
or enroll human subjects. It reuses two existing fictional SQLite schemas in
ONE database to make admission/assignment/learning-record provisioning and
supervised visit boundaries atomic. Question delivery still uses the existing
synthetic learning engine, with no external HTTP application.

This is a technical demonstration of crash-consistent SQLite transactions,
not a production study implementation or institutionally authorized release.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import uuid

from .pilot_admission_controls_draft import (
    AdmissionDenied, SyntheticAdmissionStore, _json as admission_json,
)
from .pilot_session_flow_draft import PilotSessionFlow, start_visit as flow_start
from .pilot_session_store_draft import _serialize
from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from .study_v2 import CONCEPTS, RecoveryStatus


class UnifiedSyntheticError(AdmissionDenied):
    """An atomic fictional study transition was rejected."""


class UnifiedSyntheticStudyStore:
    """Single SQLite file, never a live or network-exposed human study.

    The database name intentionally remains the admission fixture's fixed
    fictional_admission.sqlite3; the learning schema uses different tables.
    Each combined operation uses ONE BEGIN IMMEDIATE connection/commit.
    """

    def __init__(self, path: str | Path, *,
                 consent_sha256: str, screening_version: str,
                 operator_key: bytes, auditor_key: bytes,
                 items_path: str | Path, resources_path: str | Path,
                 clock=None, simulations: int = 41):
        self.admission = SyntheticAdmissionStore(
            path, consent_sha256=consent_sha256,
            screening_version=screening_version,
            operator_key=operator_key, auditor_key=auditor_key, clock=clock,
        )
        # The learning store has disjoint table names and the same absolute
        # SQLite file path. Initializing both creates one durable database.
        self.learning = SyntheticThreeArmPilotStore(
            path, items_path=items_path, resources_path=resources_path,
            simulations=simulations,
        )
        if self.admission.path.resolve() != self.learning.path.resolve():
            raise UnifiedSyntheticError("both fixtures must use the same SQLite file")
        self.path = self.admission.path
        self._version = admission_json({
            "version": "SYNTHETIC_UNIFIED_SQLITE_V1_NOT_APPROVED",
            "admission": self.admission._config,
            "learning": self.learning.policy_config,
        })
        with self.admission._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS unified_config "
                "(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS unified_links ("
                "admission_pid TEXT PRIMARY KEY REFERENCES admission_people(pid),"
                "learning_pid TEXT NOT NULL UNIQUE REFERENCES pilot_people(pid),"
                "arm TEXT NOT NULL CHECK(arm IN ('A','B','C')))"
            )
            row = db.execute("SELECT value FROM unified_config WHERE id=1").fetchone()
            if row is None:
                people = db.execute("SELECT COUNT(*) FROM admission_people").fetchone()[0]
                learner = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
                if people or learner:
                    raise UnifiedSyntheticError("cannot convert an existing populated fixture")
                db.execute("INSERT INTO unified_config VALUES(1,?)", (self._version,))
            elif row["value"] != self._version:
                raise UnifiedSyntheticError("unified fixture source or policy changed")
        self._operator_key = operator_key

    def issue_invitation(self, operator_key: bytes) -> dict:
        return self.admission.issue_invitation(operator_key)

    def screen(self, operator_key: bytes, pid: str, *,
               eligible: bool, screening_version: str) -> dict:
        return self.admission.screen(
            operator_key, pid, eligible=eligible,
            screening_version=screening_version,
        )

    @staticmethod
    def _link(db, pid: str):
        link = db.execute(
            "SELECT learning_pid,arm FROM unified_links WHERE admission_pid=?",
            (pid,),
        ).fetchone()
        if link is None:
            raise UnifiedSyntheticError("synthetic learning link is missing")
        return link

    def consent_and_create(self, invitation: str, *, agreed: bool,
                           information_sha256: str,
                           fail_at: str | None = None) -> dict:
        """Commit consent, hidden allocation and learner creation atomically.

        fail_at is a *synthetic fault-injection flag* for rollback tests only.
        No public web route imports this class.
        """
        if fail_at not in (None, "after_allocation", "after_learning"):
            raise ValueError("unknown fictional fault injection")
        if agreed is not True or information_sha256 != self.admission._consent_sha256:
            raise UnifiedSyntheticError("exact fictional information version required")
        now = self.admission._now()
        with self.admission._transaction() as db:
            row = self.admission._person(db, invitation)
            if row["status"] == "active":
                self._link(db, row["pid"])
                return {"accepted": True, "created": False,
                        "synthetic_only": True, "human_enrollment_authorized": False}
            if row["status"] != "eligible":
                raise UnifiedSyntheticError("synthetic screening is required")
            self.admission._allocate(db, row["pid"])
            slot = db.execute(
                "SELECT arm FROM admission_slots WHERE pid=?", (row["pid"],)
            ).fetchone()
            if slot is None or slot["arm"] not in "ABC":
                raise UnifiedSyntheticError("missing concealed allocation")
            arm = slot["arm"]
            db.execute(
                "UPDATE admission_people SET status='active',"
                "consent_at=?,token_expiry=? WHERE pid=?",
                (now.isoformat(), (now + timedelta(days=30)).isoformat(), row["pid"]),
            )
            self.admission._event(
                db, row["pid"], now, "fixture_consented_and_assigned",
                {"consent_sha256": self.admission._consent_sha256},
            )
            if fail_at == "after_allocation":
                raise UnifiedSyntheticError("injected fictional allocation failure")
            learning_pid = "SYN_PILOT_" + uuid.uuid4().hex
            policy = dict(
                arm=arm, mastery={concept: .2 for concept in CONCEPTS},
                used=[], recovery=asdict(RecoveryStatus()),
            )
            db.execute(
                "INSERT INTO pilot_people(pid,state,created_at) VALUES(?,?,?)",
                (learning_pid, _serialize(PilotSessionFlow()), now.isoformat()),
            )
            db.execute(
                "INSERT INTO pilot_three_arm_people(pid,arm,policy) VALUES(?,?,?)",
                (learning_pid, arm, json.dumps(policy, sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False)),
            )
            self.learning._event(
                db, learning_pid, now, "synthetic_three_arm_record_created",
                assigned_arm=arm,
            )
            if fail_at == "after_learning":
                raise UnifiedSyntheticError("injected fictional learning-link failure")
            db.execute(
                "INSERT INTO unified_links(admission_pid,learning_pid,arm) "
                "VALUES(?,?,?)",
                (row["pid"], learning_pid, arm),
            )
        return {"accepted": True, "created": True,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def operator_lookup(self, operator_key: bytes, pid: str) -> tuple[str, str]:
        """Private fixture-only learner ID and arm; no public endpoint."""
        self.admission._require(operator_key, "operator")
        if type(pid) is not str or not pid.startswith("SYN_ADMISSION_"):
            raise UnifiedSyntheticError("fictional admission ID required")
        with self.admission._transaction() as db:
            person = db.execute(
                "SELECT status FROM admission_people WHERE pid=?", (pid,)
            ).fetchone()
            if person is None or person["status"] != "active":
                raise UnifiedSyntheticError("fictional subject inactive")
            link = self._link(db, pid)
            if link["arm"] not in "ABC":
                raise UnifiedSyntheticError("fictional arm invalid")
            return link["learning_pid"], link["arm"]

    def start_visit(self, operator_key: bytes, pid: str, visit: int, *,
                    fail_at: str | None = None) -> dict:
        """All-or-nothing attendance plus learning-stage start."""
        self.admission._require(operator_key, "operator")
        if type(visit) is not int or visit not in (1, 2, 3):
            raise UnifiedSyntheticError("fictional visit must be 1, 2 or 3")
        if fail_at not in (None, "after_attendance"):
            raise ValueError("unknown fictional fault injection")
        now = self.admission._now()
        with self.admission._transaction() as db:
            person = db.execute(
                "SELECT status,consent_at FROM admission_people WHERE pid=?",
                (pid,),
            ).fetchone()
            if (person is None or person["status"] != "active"
                    or person["consent_at"] is None
                    or now < datetime.fromisoformat(person["consent_at"])):
                raise UnifiedSyntheticError("fictional active consent required")
            link = self._link(db, pid)
            prior = db.execute(
                "SELECT visit,finished_at FROM admission_visits "
                "WHERE pid=? ORDER BY visit", (pid,),
            ).fetchall()
            if len(prior) != visit - 1:
                raise UnifiedSyntheticError("fictional visit out of order")
            if prior:
                if prior[-1]["finished_at"] is None:
                    raise UnifiedSyntheticError("prior fictional visit not finished")
                gap = now - datetime.fromisoformat(prior[-1]["finished_at"])
                if not timedelta(hours=72) <= gap <= timedelta(hours=120):
                    raise UnifiedSyntheticError("fictional visit interval violation")
            state = self.learning._load(db, link["learning_pid"])
            # This is a fixture flag, not real staff authentication or release.
            updated = flow_start(
                state, visit=visit, at=now,
                staff_authorized=True, release_authorized=True,
            )
            policy = self.learning._policy(db, link["learning_pid"])
            policy["recovery"] = asdict(RecoveryStatus())
            db.execute(
                "INSERT INTO admission_visits(pid,visit,started_at) VALUES(?,?,?)",
                (pid, visit, now.isoformat()),
            )
            self.admission._event(
                db, pid, now, "fixture_visit_started", {"visit": visit},
            )
            if fail_at == "after_attendance":
                raise UnifiedSyntheticError("injected fictional attendance failure")
            self.learning._save(db, link["learning_pid"], updated)
            self.learning._save_policy(db, link["learning_pid"], policy)
            self.learning._event(
                db, link["learning_pid"], now,
                "synthetic_visit_started", visit=visit,
                assigned_arm=policy["arm"],
            )
        return {"accepted": True, "visit": visit,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def finish_visit(self, operator_key: bytes, pid: str, visit: int,
                     *, fail_at: str | None = None) -> dict:
        """Record attendance finish only when learning's visit is finished."""
        self.admission._require(operator_key, "operator")
        if type(visit) is not int or visit not in (1, 2, 3):
            raise UnifiedSyntheticError("fictional visit must be 1, 2 or 3")
        if fail_at not in (None, "after_attendance"):
            raise ValueError("unknown fictional fault injection")
        now = self.admission._now()
        with self.admission._transaction() as db:
            person = db.execute(
                "SELECT status FROM admission_people WHERE pid=?", (pid,)
            ).fetchone()
            if person is None or person["status"] != "active":
                raise UnifiedSyntheticError("fictional participation inactive")
            link = self._link(db, pid)
            row = db.execute(
                "SELECT started_at,finished_at FROM admission_visits "
                "WHERE pid=? AND visit=?", (pid, visit),
            ).fetchone()
            state = self.learning._load(db, link["learning_pid"])
            if (row is None or row["finished_at"] is not None
                    or now < datetime.fromisoformat(row["started_at"])
                    or len(state.visit_finished_at) != visit
                    or state.stage != ("complete" if visit == 3 else "awaiting_visit")):
                raise UnifiedSyntheticError(
                    "fictional attendance requires completed learning visit"
                )
            db.execute(
                "UPDATE admission_visits SET finished_at=? "
                "WHERE pid=? AND visit=?",
                (now.isoformat(), pid, visit),
            )
            if fail_at == "after_attendance":
                raise UnifiedSyntheticError("injected fictional finish failure")
            self.admission._event(
                db, pid, now, "fixture_visit_finished", {"visit": visit},
            )
        return {"accepted": True, "visit": visit,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def withdraw(self, invitation: str) -> dict:
        """Atomically stop fictional admission and invalidate learning stage.

        This is a synthetic-only tombstone, NOT a real GDPR deletion or
        institutional withdrawal workflow. Pending actions are retained for
        a fictional audit, but can no longer be submitted as live actions.
        """
        now = self.admission._now()
        with self.admission._transaction() as db:
            person = self.admission._person(
                db, invitation, allow_withdrawn=True,
            )
            if person["status"] == "withdrawn":
                return {"stopped": True, "changed": False,
                        "synthetic_only": True, "human_enrollment_authorized": False}
            link = db.execute(
                "SELECT learning_pid FROM unified_links WHERE admission_pid=?",
                (person["pid"],),
            ).fetchone()
            if person["status"] == "active" and link is None:
                raise UnifiedSyntheticError("active fictional participant lacks learner")
            if link:
                state = self.learning._load(db, link["learning_pid"])
                if state.last_event_at is not None and now < state.last_event_at:
                    raise UnifiedSyntheticError("fictional withdrawal clock precedes learning")
                updated = replace(state, stage="withdrawn", last_event_at=now)
                self.learning._save(db, link["learning_pid"], updated)
                self.learning._event(
                    db, link["learning_pid"], now,
                    "synthetic_learning_withdrawn",
                )
            db.execute(
                "UPDATE admission_people SET status='withdrawn' WHERE pid=?",
                (person["pid"],),
            )
            self.admission._event(
                db, person["pid"], now, "fixture_withdrawn", {},
            )
        return {"stopped": True, "changed": True,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def audit(self, auditor_key: bytes) -> dict:
        """Aggregate cross-subsystem audit; retains independent chain checks."""
        self.admission._require(auditor_key, "auditor")
        issues = []
        with self.admission._transaction() as db:
            active = db.execute(
                "SELECT COUNT(*) FROM admission_people WHERE status='active'"
            ).fetchone()[0]
            withdrawn_linked = db.execute(
                "SELECT COUNT(*) FROM admission_people AS p "
                "JOIN unified_links AS l ON l.admission_pid=p.pid "
                "WHERE p.status='withdrawn'"
            ).fetchone()[0]
            links = db.execute(
                "SELECT l.admission_pid,l.learning_pid,l.arm,s.arm AS assigned "
                "FROM unified_links AS l "
                "JOIN admission_slots AS s ON s.pid=l.admission_pid"
            ).fetchall()
            all_links = db.execute("SELECT COUNT(*) FROM unified_links").fetchone()[0]
            learners = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
            for link in links:
                person = db.execute(
                    "SELECT status FROM admission_people WHERE pid=?",
                    (link["admission_pid"],),
                ).fetchone()
                if person is None or person["status"] not in ("active", "withdrawn"):
                    issues.append("unified link to nonconsenting or unknown record")
                policy = db.execute(
                    "SELECT arm FROM pilot_three_arm_people WHERE pid=?",
                    (link["learning_pid"],),
                ).fetchone()
                if (link["arm"] != link["assigned"] or policy is None
                        or policy["arm"] != link["arm"]):
                    issues.append("inconsistent concealed arm or learning link")
                attendance = db.execute(
                    "SELECT visit,finished_at FROM admission_visits "
                    "WHERE pid=? ORDER BY visit",
                    (link["admission_pid"],),
                ).fetchall()
                state = self.learning._load(db, link["learning_pid"])
                if (person is not None and person["status"] == "withdrawn"
                        and state.stage != "withdrawn"):
                    issues.append("withdrawn fictional learner still active")
                if (person is not None and person["status"] == "active"
                        and state.stage == "withdrawn"):
                    issues.append("active admission paired to withdrawn learner")
                if len(attendance) != len(state.visit_started_at):
                    issues.append("admission-learning visit start mismatch")
                if sum(x["finished_at"] is not None for x in attendance) != len(state.visit_finished_at):
                    issues.append("admission-learning visit completion mismatch")
            if (all_links != len(links) or all_links != learners
                    or active + withdrawn_linked != all_links):
                issues.append("orphan, missing or inconsistent unified learning link")
        admission_audit = self.admission.audit(auditor_key)
        if admission_audit["result"] != "PASS_SYNTHETIC_ONLY":
            issues.append("independent admission audit failed")
        return {
            "result": "PASS_SYNTHETIC_ONLY" if not issues else "FAIL_SYNTHETIC",
            "issues": issues,
            "fictional_active_records": active,
            "fictional_learning_links": all_links,
            "sqlite_integrity": admission_audit["sqlite_integrity"],
            "cross_database_atomicity": True,
            "single_sqlite_file": True,
            "human_enrollment_authorized": False,
            "staff_authentication_real": False,
            "independent_security_or_ethics_approval": False,
        }
