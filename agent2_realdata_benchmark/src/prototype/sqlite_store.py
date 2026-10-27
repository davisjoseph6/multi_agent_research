"""Durable local-only quiz session repository.

SQLite protects accepted responses and sequence position
in one transaction. This is not a participant-study database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from src.prototype.item_bank import QuizItem
from src.prototype.session_engine import (
    FixedQuizSession,
    ResponseRecord,
)


class SessionNotFound(ValueError):
    pass


class ItemBankMismatch(ValueError):
    pass


class ResponseConflict(ValueError):
    pass


@dataclass(frozen=True)
class SessionProgress:
    session_id: str
    bank_version: str
    position: int
    completed: bool
    current_question: dict | None


@dataclass(frozen=True)
class SubmissionReceipt:
    """Private backend result; includes answer correctness."""

    record: ResponseRecord
    replayed: bool
    completed: bool


class SQLiteQuizRepository:
    """Single-bank, file-backed, transactional local repository."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        items: tuple[QuizItem, ...],
        bank_version: str,
    ) -> None:
        # Reuse the established validation and sequencing rules.
        FixedQuizSession(
            items=items,
            bank_version=bank_version,
        )

        if str(database_path) == ":memory:":
            raise ValueError("A file-backed database is required")

        self._path = str(Path(database_path).expanduser())
        self._items = items
        self._version = bank_version

        canonical = json.dumps(
            [asdict(item) for item in items],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        self._digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        self._initialize_database()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(
            self._path,
            timeout=10.0,
            isolation_level=None,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")

        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write_transaction(self):
        with self._connection() as connection:
            # Reserve the SQLite writer slot before inspecting
            # the current question position.
            connection.execute("BEGIN IMMEDIATE")

            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _initialize_database(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    bank_version TEXT NOT NULL,
                    bank_digest TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0
                        CHECK(position >= 0)
                );

                CREATE TABLE IF NOT EXISTS responses (
                    session_id TEXT NOT NULL,
                    position INTEGER NOT NULL
                        CHECK(position >= 0),
                    item_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    choice_id TEXT NOT NULL,
                    correct INTEGER NOT NULL
                        CHECK(correct IN (0, 1)),
                    request_id TEXT NOT NULL,

                    PRIMARY KEY(session_id, position),
                    UNIQUE(session_id, request_id),

                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                );
                """
            )

    def _session_row(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT bank_version, bank_digest, position
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        if row is None:
            raise SessionNotFound("Unknown session")

        if (
            row["bank_version"] != self._version
            or row["bank_digest"] != self._digest
        ):
            raise ItemBankMismatch(
                "Stored session uses a different item bank"
            )

        return row

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ResponseRecord:
        return ResponseRecord(
            bank_version=row["bank_version"],
            position=row["position"],
            item_id=row["item_id"],
            concept_id=row["concept_id"],
            kind=row["kind"],
            choice_id=row["choice_id"],
            correct=bool(row["correct"]),
        )

    def create_session(self) -> str:
        session_id = uuid4().hex

        with self._write_transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions
                    (session_id, bank_version, bank_digest, position)
                VALUES (?, ?, ?, 0)
                """,
                (
                    session_id,
                    self._version,
                    self._digest,
                ),
            )

        return session_id

    def read_progress(self, session_id: str) -> SessionProgress:
        with self._connection() as connection:
            row = self._session_row(
                connection,
                session_id,
            )

            position = row["position"]

        if position > len(self._items):
            raise ValueError("Stored position is invalid")

        completed = position == len(self._items)

        return SessionProgress(
            session_id=session_id,
            bank_version=self._version,
            position=position,
            completed=completed,
            current_question=(
                None
                if completed
                else self._items[position].public_dict()
            ),
        )

    def read_responses(
        self,
        session_id: str,
    ) -> tuple[ResponseRecord, ...]:
        """Private persisted history for deterministic replay."""

        with self._connection() as connection:
            self._session_row(connection, session_id)

            rows = connection.execute(
                """
                SELECT
                    ? AS bank_version,
                    position,
                    item_id,
                    concept_id,
                    kind,
                    choice_id,
                    correct
                FROM responses
                WHERE session_id = ?
                ORDER BY position
                """,
                (self._version, session_id),
            ).fetchall()

        return tuple(
            self._record_from_row(row)
            for row in rows
        )

    def _before_new_response(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        position: int,
    ) -> None:
        """Optional policy check inside the submission transaction."""
        return None

    def _after_new_response(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        position: int,
        item: QuizItem,
    ) -> None:
        """Optional policy event inside the same transaction."""
        return None

    def submit(
        self,
        *,
        session_id: str,
        item_id: str,
        choice_id: str,
        request_id: str,
    ) -> SubmissionReceipt:
        """Persist one answer or replay an identical request.

        One request_id represents one logical submission.
        A retry must reuse the original request_id.
        """

        if (
            type(request_id) is not str
            or not request_id.strip()
            or len(request_id) > 128
        ):
            raise ValueError("Invalid request identifier")

        with self._write_transaction() as connection:
            row = self._session_row(
                connection,
                session_id,
            )

            position = row["position"]

            existing = connection.execute(
                """
                SELECT
                    ? AS bank_version,
                    position,
                    item_id,
                    concept_id,
                    kind,
                    choice_id,
                    correct
                FROM responses
                WHERE session_id = ?
                  AND request_id = ?
                """,
                (self._version, session_id, request_id),
            ).fetchone()

            if existing is not None:
                if (
                    existing["item_id"] != item_id
                    or existing["choice_id"] != choice_id
                ):
                    raise ResponseConflict(
                        "Request identifier reused with "
                        "different submission data"
                    )

                # A replay describes the original submission,
                # not the session's current completion state.
                return SubmissionReceipt(
                    record=self._record_from_row(existing),
                    replayed=True,
                    completed=(
                        existing["position"] + 1
                        == len(self._items)
                    ),
                )

            if position >= len(self._items):
                raise ResponseConflict(
                    "Session already complete"
                )

            item = self._items[position]

            if (
                type(item_id) is not str
                or item_id != item.item_id
            ):
                raise ResponseConflict(
                    "Unexpected question ID"
                )

            valid_choices = {
                identifier
                for identifier, _ in item.choices
            }

            if (
                type(choice_id) is not str
                or choice_id not in valid_choices
            ):
                raise ValueError("Invalid answer choice")

            self._before_new_response(
                connection,
                session_id=session_id,
                position=position,
            )

            correct = choice_id == item.correct_id

            connection.execute(
                """
                INSERT INTO responses (
                    session_id,
                    position,
                    item_id,
                    concept_id,
                    kind,
                    choice_id,
                    correct,
                    request_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    position,
                    item.item_id,
                    item.concept_id,
                    item.kind,
                    choice_id,
                    int(correct),
                    request_id,
                ),
            )

            updated = connection.execute(
                """
                UPDATE sessions
                SET position = position + 1
                WHERE session_id = ?
                  AND position = ?
                """,
                (session_id, position),
            )

            if updated.rowcount != 1:
                raise ResponseConflict(
                    "Concurrent session position change"
                )

            self._after_new_response(
                connection,
                session_id=session_id,
                position=position,
                item=item,
            )

            record = ResponseRecord(
                bank_version=self._version,
                position=position,
                item_id=item.item_id,
                concept_id=item.concept_id,
                kind=item.kind,
                choice_id=choice_id,
                correct=correct,
            )

            return SubmissionReceipt(
                record=record,
                replayed=False,
                completed=position + 1 == len(self._items),
            )
