"""Durable, SYNTHETIC-ONLY V2 opt-in reminder queue.

Separate contact database; no research answers or arm assignments are stored.
Only .test addresses and SYN_CONTACT_* fixtures are accepted. This is not an
SMTP/email provider or an authorized human-recruitment workflow.

Reserving a reminder is transactional and unique per pause episode. The
explicit preview-delivery acknowledgment models an actual successful send;
a second notice is not due until 3 days after that acknowledgment.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
import sqlite3

from .research_v2_proposal import EMAIL_TEMPLATES, ProposedStudyError, utc


FIRST_AFTER = timedelta(days=3)
FOLLOWUP_AFTER_SEND = timedelta(days=3)
PAUSE_DEADLINE = timedelta(days=14)
CLAIM_LEASE = timedelta(minutes=30)


def _stamp(when: datetime) -> str:
    return utc(when).isoformat()


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SyntheticReminderOutbox:
    """SQLite outbox with transactional deduplication, no outbound network."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.name != "fictional_contact_outbox.sqlite3":
            raise ProposedStudyError("only a separate fictional contact database is supported")
        if self.path.is_symlink():
            raise ProposedStudyError("symlinked contact database refused")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.path.is_file() and self.path.exists():
            raise ProposedStudyError("contact database path is not a regular file")
        with self._tx() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS contacts (
                    ref TEXT PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    locale TEXT NOT NULL CHECK(locale IN ('en','fr')),
                    opted_in INTEGER NOT NULL CHECK(opted_in IN (0,1)),
                    withdrawn INTEGER NOT NULL DEFAULT 0 CHECK(withdrawn IN (0,1)),
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
                    pause_episode INTEGER NOT NULL DEFAULT 0,
                    paused_at TEXT,
                    first_delivered_at TEXT,
                    second_delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY,
                    ref TEXT NOT NULL REFERENCES contacts(ref),
                    episode INTEGER NOT NULL,
                    reminder INTEGER NOT NULL CHECK(reminder IN (1,2)),
                    reserved_at TEXT NOT NULL,
                    last_claimed_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts >= 1),
                    delivered_at TEXT,
                    UNIQUE(ref,episode,reminder)
                );
            """)
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(outbox)")
            }
            if not {"last_claimed_at", "attempts"}.issubset(columns):
                raise ProposedStudyError(
                    "old fictional contact schema cannot be upgraded in place; "
                    "create an isolated fresh test database"
                )
        os.chmod(self.path, 0o600)

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
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
    def _require_fixture(ref: str, email: str | None = None):
        if not isinstance(ref, str) or not re.fullmatch(
                r"SYN_CONTACT_[A-Za-z0-9_-]{1,64}", ref):
            raise ProposedStudyError("fictional contact reference required")
        if email is not None:
            if (not isinstance(email, str)
                    or not re.fullmatch(r"[A-Za-z0-9._+-]{1,64}@[A-Za-z0-9.-]+\.test", email)
                    or len(email) > 150):
                raise ProposedStudyError("only synthetic .test recipient addresses allowed")

    def register(self, ref: str, email: str, *, locale: str, opted_in: bool):
        self._require_fixture(ref, email)
        if locale not in EMAIL_TEMPLATES or type(opted_in) is not bool:
            raise ProposedStudyError("supported language and explicit email opt-in required")
        try:
            with self._tx() as db:
                db.execute(
                    "INSERT INTO contacts(ref,email,locale,opted_in) VALUES(?,?,?,?)",
                    (ref, email, locale, int(opted_in)),
                )
        except sqlite3.IntegrityError as exc:
            raise ProposedStudyError(
                "fictional contact or case-insensitive email already registered"
            ) from exc

    def pause(self, ref: str, at: datetime):
        self._require_fixture(ref)
        at_iso = _stamp(at)
        with self._tx() as db:
            row = db.execute(
                "SELECT withdrawn,completed,paused_at FROM contacts WHERE ref=?", (ref,)
            ).fetchone()
            if row is None or row["withdrawn"] or row["completed"] or row["paused_at"]:
                raise ProposedStudyError("cannot start a new pause episode")
            db.execute(
                "UPDATE contacts SET pause_episode=pause_episode+1,paused_at=?,"
                "first_delivered_at=NULL,second_delivered_at=NULL WHERE ref=?",
                (at_iso, ref),
            )

    def _close(self, ref: str, at: datetime, field: str):
        self._require_fixture(ref)
        now = utc(at)
        with self._tx() as db:
            row = db.execute(
                "SELECT paused_at FROM contacts WHERE ref=?", (ref,)
            ).fetchone()
            if row is None:
                raise ProposedStudyError("unknown fictional contact")
            if row["paused_at"] is not None:
                start = _time(row["paused_at"])
                if now < start:
                    raise ProposedStudyError("activity before pause")
                if field == "resume" and now - start > PAUSE_DEADLINE:
                    raise ProposedStudyError("14-day resume window expired")
            if field == "resume":
                db.execute("UPDATE contacts SET paused_at=NULL WHERE ref=?", (ref,))
            elif field == "withdraw":
                db.execute("UPDATE contacts SET withdrawn=1,paused_at=NULL WHERE ref=?", (ref,))
            elif field == "complete":
                db.execute("UPDATE contacts SET completed=1,paused_at=NULL WHERE ref=?", (ref,))
            elif field == "optout":
                db.execute("UPDATE contacts SET opted_in=0 WHERE ref=?", (ref,))

    def resume(self, ref: str, at: datetime):
        self._close(ref, at, "resume")

    def withdraw(self, ref: str, at: datetime):
        self._close(ref, at, "withdraw")

    def complete(self, ref: str, at: datetime):
        self._close(ref, at, "complete")

    def opt_out(self, ref: str, at: datetime):
        self._close(ref, at, "optout")

    @staticmethod
    def _eligible(row, now: datetime) -> bool:
        if not row["opted_in"] or row["withdrawn"] or row["completed"] or not row["paused_at"]:
            return False
        start = _time(row["paused_at"])
        return start <= now <= start + PAUSE_DEADLINE

    def reserve_due(self, at: datetime) -> tuple[int, ...]:
        """Reserve at most one message per episode per invocation, atomically.

        Returns opaque queue IDs, never contact details. Crashed claims
        become available for a re-attempt after a 30-minute lease. The same
        queue ID must be used as an idempotency key at an actual provider.
        A generic SMTP connection cannot guarantee exactly-once delivery.
        """
        now = utc(at)
        reserved = []
        with self._tx() as db:
            for row in db.execute("SELECT * FROM contacts ORDER BY ref").fetchall():
                if not self._eligible(row, now):
                    continue
                start = _time(row["paused_at"])
                if row["first_delivered_at"] is None:
                    number = 1 if now - start >= FIRST_AFTER else None
                elif row["second_delivered_at"] is None:
                    number = (2 if now - _time(row["first_delivered_at"])
                              >= FOLLOWUP_AFTER_SEND else None)
                else:
                    number = None
                if number is None:
                    continue
                exists = db.execute(
                    "SELECT id,delivered_at,last_claimed_at FROM outbox "
                    "WHERE ref=? AND episode=? AND reminder=?",
                    (row["ref"], row["pause_episode"], number),
                ).fetchone()
                if exists:
                    if exists["delivered_at"] is not None:
                        continue
                    claimed_at = _time(exists["last_claimed_at"])
                    if now < claimed_at:
                        raise ProposedStudyError("claim clock moved backward")
                    if now - claimed_at < CLAIM_LEASE:
                        continue
                    db.execute(
                        "UPDATE outbox SET last_claimed_at=?,attempts=attempts+1 "
                        "WHERE id=?",
                        (_stamp(now), exists["id"]),
                    )
                    reserved.append(exists["id"])
                    continue
                cur = db.execute(
                    "INSERT INTO outbox(ref,episode,reminder,reserved_at,"
                    "last_claimed_at) VALUES(?,?,?,?,?)",
                    (row["ref"], row["pause_episode"], number,
                     _stamp(now), _stamp(now)),
                )
                reserved.append(cur.lastrowid)
        return tuple(reserved)

    def preview_payload(self, queue_id: int, at: datetime) -> dict:
        """For the private fictional local worker only. Never expose via HTTP.

        Returns only a reserved .test address, localized subject/body and
        stable fictional provider idempotency key, never arm assignment.
        A real provider integration needs additional reviewed release gates.
        """
        if type(queue_id) is not int or queue_id <= 0:
            raise ProposedStudyError("invalid fictional outbox id")
        now = utc(at)
        with self._tx() as db:
            row = db.execute(
                "SELECT o.*,c.email,c.locale,c.opted_in,c.withdrawn,c.completed,"
                "c.paused_at,c.pause_episode,c.first_delivered_at,c.second_delivered_at "
                "FROM outbox o JOIN contacts c ON o.ref=c.ref WHERE o.id=?",
                (queue_id,),
            ).fetchone()
            if (row is None or row["delivered_at"] is not None
                    or row["episode"] != row["pause_episode"]
                    or not self._eligible(row, now)):
                raise ProposedStudyError("inactive fictional outbox reservation")
            claimed = _time(row["last_claimed_at"])
            if not claimed <= now < claimed + CLAIM_LEASE:
                raise ProposedStudyError("fictional outbox claim lease expired")
            if row["reminder"] == 1:
                valid = (row["first_delivered_at"] is None
                         and now - _time(row["paused_at"]) >= FIRST_AFTER)
            else:
                valid = (row["first_delivered_at"] is not None
                         and row["second_delivered_at"] is None
                         and now - _time(row["first_delivered_at"])
                         >= FOLLOWUP_AFTER_SEND)
            if not valid:
                raise ProposedStudyError("fictional message not yet due")
            if not row["email"].lower().endswith(".test"):
                raise ProposedStudyError("refusing nonfictional contact")
            template = EMAIL_TEMPLATES[row["locale"]][
                f"reminder_{row['reminder']}"
            ]
            subject = (
                "Fictional study reminder"
                if row["locale"] == "en" else "Rappel d'étude fictive"
            )
            return {
                "recipient": row["email"], "subject": subject,
                "body": template, "locale": row["locale"],
                "preview_idempotency_key": f"SYN_V2_REMINDER_{queue_id}",
                "synthetic_only": True,
            }

    def deliver_preview(self, queue_id: int, at: datetime) -> dict:
        """Commit fictional delivery only, without network or real email.

        Stale claims after withdrawal/resume/episode rollover are rejected.
        """
        if type(queue_id) is not int or queue_id <= 0:
            raise ProposedStudyError("invalid fictional outbox id")
        now = utc(at)
        with self._tx() as db:
            row = db.execute(
                "SELECT o.*,c.email,c.locale,c.opted_in,c.withdrawn,c.completed,"
                "c.paused_at,c.pause_episode,c.first_delivered_at,c.second_delivered_at "
                "FROM outbox o JOIN contacts c ON o.ref=c.ref WHERE o.id=?",
                (queue_id,),
            ).fetchone()
            if row is None:
                raise ProposedStudyError("unknown fictional outbox entry")
            if row["delivered_at"]:
                return {"preview_delivered": True, "replayed": True, "id": queue_id}
            if (not self._eligible(row, now)
                    or row["episode"] != row["pause_episode"]):
                raise ProposedStudyError("withdrawn, resumed or expired reminder withheld")
            first = row["first_delivered_at"]
            start = _time(row["paused_at"])
            if row["reminder"] == 1:
                valid = first is None and now - start >= FIRST_AFTER
            else:
                valid = (first is not None and row["second_delivered_at"] is None
                         and now - _time(first) >= FOLLOWUP_AFTER_SEND)
            if not valid:
                raise ProposedStudyError("preview delivery is premature or out of sequence")
            column = "first_delivered_at" if row["reminder"] == 1 else "second_delivered_at"
            db.execute("UPDATE outbox SET delivered_at=? WHERE id=?", (_stamp(now), queue_id))
            db.execute(f"UPDATE contacts SET {column}=? WHERE ref=?", (_stamp(now), row["ref"]))
            # Do not return the recipient, arm assignment, or the email body.
            return {"preview_delivered": True, "replayed": False,
                    "id": queue_id, "reminder": row["reminder"],
                    "locale": row["locale"], "synthetic_only": True}

    def inspect_redacted(self, ref: str) -> dict:
        """Operational diagnostics without exposing email or answer data."""
        self._require_fixture(ref)
        with self._tx() as db:
            row = db.execute(
                "SELECT locale,opted_in,withdrawn,completed,pause_episode,paused_at "
                "FROM contacts WHERE ref=?", (ref,)
            ).fetchone()
            if row is None:
                raise ProposedStudyError("unknown fictional contact")
            return dict(row) | {"synthetic_only": True}
