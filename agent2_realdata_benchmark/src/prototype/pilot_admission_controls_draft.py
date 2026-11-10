"""Disconnected synthetic admission, allocation and visit-scheduling contract.

This module intentionally has NO Flask routes, participant identity collection,
approval API, deployment entrypoint, or mechanism to enroll a human. It is a
transactional engineering rehearsal of candidate controls that must be adapted
and independently reviewed for a genuinely authorized human-study system.

Operator and auditor keys are fixture capabilities, NOT verified staff identity.
Injected clock and fixture eligibility are NOT real screening/supervision.
Only explicitly synthetic identifiers and a specially named disposable SQLite
file are accepted. Never point this at real students or a live study database.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import os
import secrets
import sqlite3
from typing import Callable
import uuid


class AdmissionDenied(ValueError):
    """A fail-closed synthetic admission or session transition."""


SCHEMA = "IJCAI2027_SYNTHETIC_ADMISSION_V1"
ARMS = ("A", "B", "C")
DB_NAME = "fictional_admission.sqlite3"
STATUS = ("invited", "eligible", "ineligible", "active", "withdrawn")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AdmissionDenied("timezone-aware server clock required")
    return value.astimezone(timezone.utc)


class SyntheticAdmissionStore:
    """Offline-only SQLite state machine with concealed synthetic assignments.

    No caller can override the arm, declare institutional authorization, or
    supply a participant time through any of the public methods.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        consent_sha256: str,
        screening_version: str,
        operator_key: bytes,
        auditor_key: bytes,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        if (self.path.name != DB_NAME or self.path.is_symlink()
                or (self.path.exists() and not self.path.is_file())):
            raise AdmissionDenied("synthetic-only named SQLite file required")
        if self.path.parent.is_symlink():
            raise AdmissionDenied("symlink database directory rejected")
        if (type(consent_sha256) is not str or len(consent_sha256) != 64
                or any(c not in "0123456789abcdef" for c in consent_sha256)):
            raise AdmissionDenied("versioned 64-hex information digest required")
        if (type(screening_version) is not str
                or not 1 <= len(screening_version) <= 80):
            raise AdmissionDenied("versioned eligibility screening required")
        if (type(operator_key) is not bytes or len(operator_key) < 32
                or type(auditor_key) is not bytes or len(auditor_key) < 32
                or compare_digest(operator_key, auditor_key)):
            raise AdmissionDenied("separate strong offline fixture capabilities required")
        self._operator = operator_key
        self._auditor = auditor_key
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._consent_sha256 = consent_sha256
        self._screening_version = screening_version
        self._config = _json({
            "schema": SCHEMA, "consent_sha256": consent_sha256,
            "screening_version": screening_version,
            "allocation": "server_only_random_permuted_blocks_6_or_9",
            "minimum_intervisit_hours": 72,
            "maximum_intervisit_hours": 120,
            "synthetic_only": True,
        })
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as conn:
            original = {row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )}
            if original and "admission_config" not in original:
                raise AdmissionDenied("unrelated existing database forbidden")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS admission_config "
                "(id INTEGER PRIMARY KEY CHECK (id=1), config TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS admission_people "
                "(pid TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, "
                "token_expiry TEXT NOT NULL, status TEXT NOT NULL, "
                "screened_at TEXT, consent_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS admission_slots "
                "(seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "block_id INTEGER NOT NULL, arm TEXT NOT NULL, "
                "pid TEXT UNIQUE REFERENCES admission_people(pid))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS admission_visits "
                "(pid TEXT NOT NULL REFERENCES admission_people(pid), "
                "visit INTEGER NOT NULL CHECK (visit BETWEEN 1 AND 3), "
                "started_at TEXT NOT NULL, finished_at TEXT, "
                "PRIMARY KEY(pid,visit))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS admission_events "
                "(seq INTEGER PRIMARY KEY AUTOINCREMENT, pid TEXT NOT NULL, "
                "at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, "
                "prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL)"
            )
            row = conn.execute(
                "SELECT config FROM admission_config WHERE id=1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO admission_config VALUES(1,?)", (self._config,)
                )
            elif row["config"] != self._config:
                raise AdmissionDenied("frozen protocol changed: new database required")
        self.path.chmod(0o600)

    @contextmanager
    def _transaction(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _now(self) -> datetime:
        return _time(self._clock())

    def _require(self, supplied: bytes, role: str) -> None:
        expected = self._auditor if role == "auditor" else self._operator
        if type(supplied) is not bytes or not compare_digest(supplied, expected):
            raise AdmissionDenied("unverified offline fixture capability")

    @staticmethod
    def _event(conn, pid: str, at: datetime, kind: str, payload: dict) -> None:
        previous = conn.execute(
            "SELECT event_hash FROM admission_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = previous["event_hash"] if previous else "0" * 64
        timestamp = at.isoformat()
        content = _json({"pid": pid, "at": timestamp, "kind": kind,
                         "payload": payload, "prev_hash": prev_hash})
        conn.execute(
            "INSERT INTO admission_events(pid,at,kind,payload,prev_hash,event_hash)"
            " VALUES(?,?,?,?,?,?)",
            (pid, timestamp, kind, _json(payload), prev_hash, _hash(content)),
        )

    def _person(self, conn, invitation: str, *, allow_withdrawn=False):
        if type(invitation) is not str or not 32 <= len(invitation) <= 128:
            raise AdmissionDenied("invalid synthetic invitation")
        row = conn.execute(
            "SELECT * FROM admission_people WHERE token_hash=?",
            (_hash(invitation),),
        ).fetchone()
        if row is None or self._now() > datetime.fromisoformat(row["token_expiry"]):
            raise AdmissionDenied("invalid or expired synthetic invitation")
        if row["status"] == "withdrawn" and not allow_withdrawn:
            raise AdmissionDenied("synthetic participation withdrawn")
        return row

    def issue_invitation(self, operator_key: bytes, *, lifetime_hours: int = 72) -> dict:
        self._require(operator_key, "operator")
        if type(lifetime_hours) is not int or not 1 <= lifetime_hours <= 720:
            raise AdmissionDenied("bounded invitation lifetime required")
        pid = "SYN_ADMISSION_" + uuid.uuid4().hex
        invitation = secrets.token_urlsafe(32)
        now = self._now()
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO admission_people "
                "(pid,token_hash,token_expiry,status) VALUES(?,?,?,'invited')",
                (pid, _hash(invitation), (now + timedelta(hours=lifetime_hours)).isoformat()),
            )
            self._event(conn, pid, now, "synthetic_invitation_issued",
                        {"screening_version": self._screening_version})
        return {"synthetic_pid": pid, "private_invitation": invitation,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def screen(self, operator_key: bytes, pid: str, *,
               eligible: bool, screening_version: str) -> dict:
        self._require(operator_key, "operator")
        if type(eligible) is not bool or screening_version != self._screening_version:
            raise AdmissionDenied("exact synthetic eligibility decision required")
        now = self._now()
        with self._transaction() as conn:
            row = conn.execute("SELECT status,token_expiry FROM admission_people WHERE pid=?", (pid,)).fetchone()
            if (row is None or row["status"] != "invited"
                    or not pid.startswith("SYN_ADMISSION_")):
                raise AdmissionDenied("synthetic invitation not pending screening")
            if now > datetime.fromisoformat(row["token_expiry"]):
                raise AdmissionDenied("expired synthetic screening invitation")
            state = "eligible" if eligible else "ineligible"
            conn.execute(
                "UPDATE admission_people SET status=?,screened_at=? WHERE pid=?",
                (state, now.isoformat(), pid),
            )
            self._event(conn, pid, now, "fixture_screened", {"eligible": eligible})
        return {"status": state, "synthetic_only": True}

    @staticmethod
    def _allocate(conn, pid: str) -> None:
        slot = conn.execute(
            "SELECT seq FROM admission_slots WHERE pid IS NULL "
            "ORDER BY seq LIMIT 1"
        ).fetchone()
        if slot is None:
            rng = secrets.SystemRandom()
            arms = list(ARMS) * rng.choice((2, 3))
            rng.shuffle(arms)
            block_id = conn.execute(
                "SELECT COALESCE(MAX(block_id), 0)+1 FROM admission_slots"
            ).fetchone()[0]
            conn.executemany(
                "INSERT INTO admission_slots(block_id,arm) VALUES(?,?)",
                ((block_id, arm) for arm in arms),
            )
            slot = conn.execute(
                "SELECT seq FROM admission_slots WHERE pid IS NULL "
                "ORDER BY seq LIMIT 1"
            ).fetchone()
        updated = conn.execute(
            "UPDATE admission_slots SET pid=? WHERE seq=? AND pid IS NULL",
            (pid, slot["seq"]),
        )
        if updated.rowcount != 1:
            raise AdmissionDenied("atomic synthetic allocation failed")

    def consent(self, invitation: str, *, agreed: bool,
                information_sha256: str) -> dict:
        if agreed is not True or information_sha256 != self._consent_sha256:
            raise AdmissionDenied("exact information version and agreement required")
        now = self._now()
        with self._transaction() as conn:
            person = self._person(conn, invitation)
            if person["status"] == "active":
                return {"accepted": True, "created": False,
                        "synthetic_only": True, "human_enrollment_authorized": False}
            if person["status"] != "eligible":
                raise AdmissionDenied("prior staff fixture screening required")
            self._allocate(conn, person["pid"])
            conn.execute(
                "UPDATE admission_people SET status='active',consent_at=?,token_expiry=? "
                "WHERE pid=?",
                (now.isoformat(), (now + timedelta(days=30)).isoformat(),
                 person["pid"]),
            )
            self._event(conn, person["pid"], now, "fixture_consented_and_assigned",
                        {"consent_sha256": self._consent_sha256})
        return {"accepted": True, "created": True,
                "synthetic_only": True, "human_enrollment_authorized": False}

    def participant_status(self, invitation: str) -> dict:
        with self._transaction() as conn:
            row = self._person(conn, invitation, allow_withdrawn=True)
            visits = conn.execute(
                "SELECT visit,finished_at FROM admission_visits WHERE pid=? "
                "ORDER BY visit", (row["pid"],),
            ).fetchall()
        return {
            "status": row["status"],
            "visits_started": len(visits),
            "visits_finished": sum(v["finished_at"] is not None for v in visits),
            "synthetic_only": True,
            "human_enrollment_authorized": False,
        }

    def start_visit(self, operator_key: bytes, pid: str, visit: int) -> dict:
        self._require(operator_key, "operator")
        if type(visit) is not int or visit not in (1, 2, 3):
            raise AdmissionDenied("only visits 1–3 are allowed")
        now = self._now()
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT status,consent_at FROM admission_people WHERE pid=?", (pid,)
            ).fetchone()
            if row is None or row["status"] != "active" or not pid.startswith("SYN_ADMISSION_"):
                raise AdmissionDenied("synthetic active and consented state required")
            if row["consent_at"] is None or now < datetime.fromisoformat(row["consent_at"]):
                raise AdmissionDenied("synthetic visit must follow agreement")
            visits = conn.execute(
                "SELECT visit,started_at,finished_at FROM admission_visits "
                "WHERE pid=? ORDER BY visit", (pid,),
            ).fetchall()
            if len(visits) != visit - 1:
                raise AdmissionDenied("visit already started or out of order")
            if visits:
                prior = visits[-1]
                if prior["finished_at"] is None:
                    raise AdmissionDenied("prior visit not completed")
                gap = now - datetime.fromisoformat(prior["finished_at"])
                if not timedelta(hours=72) <= gap <= timedelta(hours=120):
                    raise AdmissionDenied("72–120-hour elapsed visit gap required")
            conn.execute(
                "INSERT INTO admission_visits(pid,visit,started_at) VALUES(?,?,?)",
                (pid, visit, now.isoformat()),
            )
            self._event(conn, pid, now, "fixture_visit_started", {"visit": visit})
        return {"visit": visit, "status": "started", "synthetic_only": True}

    def finish_visit(self, operator_key: bytes, pid: str, visit: int) -> dict:
        self._require(operator_key, "operator")
        if type(visit) is not int or visit not in (1, 2, 3):
            raise AdmissionDenied("only visits 1–3 are allowed")
        now = self._now()
        with self._transaction() as conn:
            person = conn.execute(
                "SELECT status FROM admission_people WHERE pid=?", (pid,)
            ).fetchone()
            row = conn.execute(
                "SELECT started_at,finished_at FROM admission_visits "
                "WHERE pid=? AND visit=?", (pid, visit)
            ).fetchone()
            if (person is None or person["status"] != "active" or row is None
                    or row["finished_at"] is not None
                    or now < datetime.fromisoformat(row["started_at"])):
                raise AdmissionDenied("visit cannot be completed in this state")
            conn.execute(
                "UPDATE admission_visits SET finished_at=? WHERE pid=? AND visit=?",
                (now.isoformat(), pid, visit),
            )
            self._event(conn, pid, now, "fixture_visit_finished", {"visit": visit})
        return {"visit": visit, "status": "finished", "synthetic_only": True}

    def withdraw(self, invitation: str) -> dict:
        now = self._now()
        with self._transaction() as conn:
            person = self._person(conn, invitation, allow_withdrawn=True)
            if person["status"] != "withdrawn":
                conn.execute(
                    "UPDATE admission_people SET status='withdrawn' WHERE pid=?",
                    (person["pid"],),
                )
                self._event(conn, person["pid"], now, "fixture_withdrawn", {})
        return {"stopped": True, "synthetic_only": True,
                "human_enrollment_authorized": False}

    def audit(self, auditor_key: bytes) -> dict:
        """Restricted synthetic-only integrity report. Never exports tokens."""
        self._require(auditor_key, "auditor")
        failures = []
        with self._transaction() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                failures.append("sqlite integrity failed")
            config = conn.execute(
                "SELECT config FROM admission_config WHERE id=1"
            ).fetchone()
            if config is None or config["config"] != self._config:
                failures.append("immutable synthetic configuration mismatch")
            allocated = conn.execute(
                "SELECT block_id,arm,pid FROM admission_slots ORDER BY seq"
            ).fetchall()
            blocks = {}
            for slot in allocated:
                blocks.setdefault(slot["block_id"], []).append(slot["arm"])
            for group in blocks.values():
                size = len(group)
                if size not in (6, 9) or any(group.count(arm) != size // 3 for arm in ARMS):
                    failures.append("randomized block is unbalanced")
            people = conn.execute(
                "SELECT status,COUNT(*) n FROM admission_people GROUP BY status"
            ).fetchall()
            # Validate the global append-only hash chain (detects corruption,
            # not a malicious actor with full database write permissions).
            previous = "0" * 64
            events = conn.execute(
                "SELECT pid,at,kind,payload,prev_hash,event_hash "
                "FROM admission_events ORDER BY seq"
            ).fetchall()
            for item in events:
                canonical_event = _json({
                    "pid": item["pid"], "at": item["at"], "kind": item["kind"],
                    "payload": json.loads(item["payload"]),
                    "prev_hash": previous,
                })
                if (item["prev_hash"] != previous
                        or not compare_digest(item["event_hash"], _hash(canonical_event))):
                    failures.append("synthetic event hash chain invalid")
                    break
                previous = item["event_hash"]
            assigned_pids = [row["pid"] for row in allocated if row["pid"] is not None]
            assigned_set = set(assigned_pids)
            if len(assigned_pids) != len(assigned_set):
                failures.append("duplicate synthetic allocation")
            people_detail = conn.execute(
                "SELECT pid,status,screened_at,consent_at "
                "FROM admission_people ORDER BY pid"
            ).fetchall()
            for person in people_detail:
                pid = person["pid"]
                if not pid.startswith("SYN_ADMISSION_"):
                    failures.append("nonfictional participant ID")
                status = person["status"]
                screened = person["screened_at"] is not None
                consented = person["consent_at"] is not None
                if status not in STATUS:
                    failures.append("unknown synthetic participation state")
                if status == "active" and (
                    not screened or not consented or pid not in assigned_set
                ):
                    failures.append("active record without screening, consent or assignment")
                if status in ("invited", "eligible", "ineligible") and (
                    consented or pid in assigned_set
                ):
                    failures.append("premature synthetic assignment or consent")
                if status in ("eligible", "ineligible") and not screened:
                    failures.append("missing synthetic screening timestamp")
                if status == "withdrawn" and consented and pid not in assigned_set:
                    failures.append("withdrawn consenting record without allocation")
                visits = conn.execute(
                    "SELECT visit,started_at,finished_at FROM admission_visits "
                    "WHERE pid=? ORDER BY visit", (pid,),
                ).fetchall()
                if visits and not consented:
                    failures.append("synthetic visit before agreement")
                for expected_visit, visit in enumerate(visits, start=1):
                    if visit["visit"] != expected_visit:
                        failures.append("out-of-order synthetic visit")
                    try:
                        started = datetime.fromisoformat(visit["started_at"])
                        if consented and started < datetime.fromisoformat(person["consent_at"]):
                            failures.append("synthetic visit before consent")
                        if visit["finished_at"] is not None:
                            finished = datetime.fromisoformat(visit["finished_at"])
                            if finished < started:
                                failures.append("invalid visit ordering")
                        if expected_visit > 1:
                            previous_visit = visits[expected_visit - 2]
                            if previous_visit["finished_at"] is None:
                                failures.append("visit before prior completion")
                            else:
                                gap = started - datetime.fromisoformat(previous_visit["finished_at"])
                                if not timedelta(hours=72) <= gap <= timedelta(hours=120):
                                    failures.append("intervisit gap outside 72–120 hours")
                    except (TypeError, ValueError):
                        failures.append("invalid synthetic visit timestamp")
        return {
            "result": "PASS_SYNTHETIC_ONLY" if not failures else "FAIL_SYNTHETIC",
            "issues": failures,
            "counts_by_status": {row["status"]: row["n"] for row in people},
            "allocated": sum(row["pid"] is not None for row in allocated),
            "block_count": len(blocks),
            "events": len(events),
            "sqlite_integrity": integrity,
            "synthetic_only": True,
            "human_enrollment_authorized": False,
            "staff_identity_independently_verified": False,
            "scientific_or_ethics_approval": False,
        }

    def backup(self, auditor_key: bytes, destination: str | Path) -> dict:
        """Create a verified *fictional-only* SQLite backup; never overwrite.

        This is an isolated software rehearsal, not an offsite encrypted
        retention or production disaster-recovery solution.
        """
        self._require(auditor_key, "auditor")
        target = Path(destination)
        if (target.name != "fictional_admission_backup.sqlite3"
                or target.is_symlink() or target.exists()
                or target.parent.is_symlink()
                or not target.parent.is_dir()):
            raise AdmissionDenied("new, nonsymlink synthetic backup target required")
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            with sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=ro", uri=True
            ) as source:
                with sqlite3.connect(target) as replica:
                    source.backup(replica)
                    integrity = replica.execute(
                        "PRAGMA integrity_check"
                    ).fetchone()[0]
                    if integrity != "ok":
                        raise AdmissionDenied("synthetic backup integrity check failed")
                    row = replica.execute(
                        "SELECT config FROM admission_config WHERE id=1"
                    ).fetchone()
                    if row is None or row[0] != self._config:
                        raise AdmissionDenied("synthetic backup configuration mismatch")
            os.chmod(target, 0o600)
        except BaseException:
            # Remove only the file created by this invocation, not a
            # pre-existing unrelated file (O_EXCL blocks overwrite).
            if target.exists() and not target.is_symlink():
                target.unlink()
            raise
        return {
            "result": "PASS_SYNTHETIC_BACKUP_ONLY",
            "sqlite_integrity": "ok",
            "synthetic_only": True,
            "human_enrollment_authorized": False,
            "offsite_restore_verified": False,
        }
