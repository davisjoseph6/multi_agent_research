"""Invitation-controlled synthetic enrollment.

Development-only. Not connected to public HTTP routes.
No real participants, personal data, or approved study.

An invitation is a high-entropy bearer credential.
Only its SHA-256 digest is stored in SQLite.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.prototype.experimental_session_store import (
    SQLiteExperimentalQuizRepository,
)
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)
from src.prototype.trial_allocation import (
    SQLiteTrialAllocationStore,
)


_TOKEN_PATTERN = re.compile(r"inv1_[0-9a-f]{64}")


class InvalidInvitation(ValueError):
    """Unknown or malformed invitation credential."""


class InvitationIntegrityError(RuntimeError):
    """Invitation binding disagrees with allocation."""


@dataclass(frozen=True)
class InvitationReceipt:
    session_id: str
    replayed: bool


class SQLiteInvitationEnrollmentStore:
    """Durable invitation-to-allocation-to-session binding."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        threshold: float = 0.30,
        block_sizes: tuple[int, ...] = (6, 9),
    ) -> None:

        if str(database_path) == ":memory:":
            raise ValueError("File-backed SQLite required")

        self._path = str(
            Path(database_path).expanduser()
        )

        self._allocator = SQLiteTrialAllocationStore(
            self._path,
            block_sizes=block_sizes,
        )

        self._quiz = SQLiteExperimentalQuizRepository(
            self._path,
            items=INSTRUCTIONAL_DEMO_ITEMS,
            bank_version=INSTRUCTIONAL_DEMO_VERSION,
            threshold=threshold,
        )

        with self._transaction() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS
                trial_invitations (
                    token_digest TEXT PRIMARY KEY,

                    participant_id TEXT UNIQUE,

                    created_at TEXT NOT NULL DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                    FOREIGN KEY(participant_id)
                        REFERENCES trial_allocations(
                            participant_id
                        )
                )
                """
            )

    @contextmanager
    def _transaction(self):

        db = sqlite3.connect(
            self._path,
            timeout=10.0,
            isolation_level=None,
        )

        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")

        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()

        except BaseException:
            db.rollback()
            raise

        finally:
            db.close()

    @staticmethod
    def _digest(token: str) -> str:

        if (
            type(token) is not str
            or _TOKEN_PATTERN.fullmatch(token) is None
        ):
            raise InvalidInvitation(
                "Invalid invitation credential"
            )

        return hashlib.sha256(
            token.encode("ascii")
        ).hexdigest()

    def issue_invitation(self) -> str:
        """Trusted local backend operation only.

        Never expose this method as a public HTTP route.
        """

        token = "inv1_" + secrets.token_hex(32)
        digest = self._digest(token)

        with self._transaction() as db:
            db.execute(
                """
                INSERT INTO trial_invitations
                (token_digest)
                VALUES (?)
                """,
                (digest,),
            )

        return token

    def redeem_invitation(
        self,
        token: str,
    ) -> InvitationReceipt:
        """Recover or create one synthetic allocated session.

        This uses recoverable, idempotent transactions:
        invitation validation -> allocation ->
        quiz binding -> invitation binding.

        Reuse of the same invitation recovers the same
        participant allocation and quiz session.
        """

        digest = self._digest(token)

        with self._transaction() as db:

            row = db.execute(
                """
                SELECT participant_id
                FROM trial_invitations
                WHERE token_digest = ?
                """,
                (digest,),
            ).fetchone()

            if row is None:
                raise InvalidInvitation(
                    "Invalid invitation credential"
                )

        # A stable, opaque request ID ensures that retries
        # cannot create a different allocation.
        request_id = "invite-v1-" + digest

        assignment = self._allocator.allocate(
            enrollment_request_id=request_id
        )

        session_id = (
            self._quiz.create_session_for_participant(
                participant_id=assignment.participant_id
            )
        )

        with self._transaction() as db:

            row = db.execute(
                """
                SELECT participant_id
                FROM trial_invitations
                WHERE token_digest = ?
                """,
                (digest,),
            ).fetchone()

            if row is None:
                raise InvitationIntegrityError(
                    "Invitation disappeared during redemption"
                )

            existing = row["participant_id"]

            if (
                existing is not None
                and existing != assignment.participant_id
            ):
                raise InvitationIntegrityError(
                    "Invitation allocation mismatch"
                )

            replayed = existing is not None

            if existing is None:
                db.execute(
                    """
                    UPDATE trial_invitations
                    SET participant_id = ?
                    WHERE token_digest = ?
                      AND participant_id IS NULL
                    """,
                    (
                        assignment.participant_id,
                        digest,
                    ),
                )

        return InvitationReceipt(
            session_id=session_id,
            replayed=replayed,
        )
