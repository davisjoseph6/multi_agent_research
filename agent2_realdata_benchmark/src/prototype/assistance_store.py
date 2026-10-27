"""Durable, local-only assistance-offer event ledger.

Fixed demonstration resource only. Does not execute
POMCP recommendations or infer actual resource uptake.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.prototype.assistance import DEMO_SUMMARY
from src.prototype.item_bank import QuizItem
from src.prototype.sqlite_store import SQLiteQuizRepository


class AssistanceConflict(ValueError):
    """Invalid, stale, or conflicting assistance operation."""


@dataclass(frozen=True)
class OfferSnapshot:
    source_position: int
    target_position: int
    resource_id: str
    title: str
    status: str
    body: str | None


class SQLiteAssistanceRepository(SQLiteQuizRepository):
    """Extends the local SQLite quiz repository with offers."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        items: tuple[QuizItem, ...],
        bank_version: str,
    ) -> None:
        super().__init__(
            database_path,
            items=items,
            bank_version=bank_version,
        )

        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS assistance_offers (
                    session_id TEXT NOT NULL,
                    source_position INTEGER NOT NULL,
                    target_position INTEGER NOT NULL,
                    resource_id TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK(status IN (
                            'offered', 'accepted', 'declined', 'delivered'
                        )),
                    PRIMARY KEY(session_id, source_position),
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS assistance_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    source_position INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    ),
                    UNIQUE(
                        session_id, source_position, event_type
                    ),
                    FOREIGN KEY(session_id, source_position)
                        REFERENCES assistance_offers(
                            session_id, source_position
                        )
                );
                """
            )

    @staticmethod
    def _snapshot(row) -> OfferSnapshot:
        delivered = row["status"] == "delivered"

        return OfferSnapshot(
            source_position=row["source_position"],
            target_position=row["target_position"],
            resource_id=row["resource_id"],
            title=DEMO_SUMMARY.title,
            status=row["status"],
            body=DEMO_SUMMARY.body if delivered else None,
        )

    @staticmethod
    def _event(
        connection,
        session_id: str,
        source_position: int,
        event_type: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO assistance_events (
                session_id, source_position, event_type
            ) VALUES (?, ?, ?)
            """,
            (session_id, source_position, event_type),
        )

    def offer_after_practice(
        self,
        *,
        session_id: str,
        source_position: int,
    ) -> OfferSnapshot:
        """Create one fixed-policy demo offer at an eligible boundary."""

        if type(source_position) is not int or source_position < 0:
            raise ValueError("Invalid source position")

        with self._write_transaction() as connection:
            state = self._session_row(connection, session_id)

            prior = connection.execute(
                """
                SELECT *
                FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            if prior is not None:
                return self._snapshot(prior)

            target_position = source_position + 1

            if (
                state["position"] != target_position
                or target_position >= len(self._items)
            ):
                raise AssistanceConflict(
                    "No eligible upcoming practice item"
                )

            previous = connection.execute(
                """
                SELECT kind, concept_id
                FROM responses
                WHERE session_id = ? AND position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            target = self._items[target_position]

            if (
                previous is None
                or previous["kind"] != "practice"
                or previous["concept_id"] != DEMO_SUMMARY.concept_id
                or target.kind != "practice"
                or target.concept_id != DEMO_SUMMARY.concept_id
            ):
                raise AssistanceConflict(
                    "Assistance is not eligible at this boundary"
                )

            connection.execute(
                """
                INSERT INTO assistance_offers (
                    session_id, source_position,
                    target_position, resource_id, status
                ) VALUES (?, ?, ?, ?, 'offered')
                """,
                (
                    session_id,
                    source_position,
                    target_position,
                    DEMO_SUMMARY.resource_id,
                ),
            )

            self._event(
                connection, session_id, source_position, "proposed"
            )
            self._event(
                connection, session_id, source_position, "offered"
            )

            row = connection.execute(
                """
                SELECT * FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            return self._snapshot(row)

    def decide(
        self,
        *,
        session_id: str,
        source_position: int,
        accept: bool,
    ) -> OfferSnapshot:
        """Record explicit acceptance or refusal atomically."""

        if type(source_position) is not int or source_position < 0:
            raise ValueError("Invalid source position")

        if type(accept) is not bool:
            raise TypeError("accept must be explicitly boolean")

        with self._write_transaction() as connection:
            state = self._session_row(connection, session_id)

            row = connection.execute(
                """
                SELECT * FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            if row is None:
                raise AssistanceConflict("Offer does not exist")

            expected = "accepted" if accept else "declined"

            if (
                row["status"] == expected
                or (accept and row["status"] == "delivered")
            ):
                return self._snapshot(row)

            if row["status"] != "offered":
                raise AssistanceConflict(
                    "Offer has an incompatible final decision"
                )

            if state["position"] != row["target_position"]:
                raise AssistanceConflict(
                    "Offer decision is no longer timely"
                )

            connection.execute(
                """
                UPDATE assistance_offers
                SET status = ?
                WHERE session_id = ? AND source_position = ?
                """,
                (expected, session_id, source_position),
            )

            if accept:
                self._event(
                    connection, session_id,
                    source_position, "accepted"
                )
            else:
                self._event(
                    connection, session_id,
                    source_position, "declined"
                )

            updated = connection.execute(
                """
                SELECT * FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            return self._snapshot(updated)

    def deliver(
        self,
        *,
        session_id: str,
        source_position: int,
    ) -> OfferSnapshot:
        """Make an explicitly accepted resource available.

        This proves backend release, not browser display
        or actual learner uptake.
        """

        if type(source_position) is not int or source_position < 0:
            raise ValueError("Invalid source position")

        with self._write_transaction() as connection:
            state = self._session_row(connection, session_id)

            row = connection.execute(
                """
                SELECT * FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            if row is None:
                raise AssistanceConflict("Offer does not exist")

            if row["status"] == "delivered":
                return self._snapshot(row)

            if row["status"] != "accepted":
                raise AssistanceConflict(
                    "Resource has not been accepted"
                )

            if state["position"] != row["target_position"]:
                raise AssistanceConflict(
                    "Resource delivery is no longer timely"
                )

            connection.execute(
                """
                UPDATE assistance_offers
                SET status = 'delivered'
                WHERE session_id = ? AND source_position = ?
                  AND status = 'accepted'
                """,
                (session_id, source_position),
            )

            self._event(
                connection, session_id,
                source_position, "delivered"
            )

            updated = connection.execute(
                """
                SELECT * FROM assistance_offers
                WHERE session_id = ? AND source_position = ?
                """,
                (session_id, source_position),
            ).fetchone()

            return self._snapshot(updated)

    def read_events(
        self,
        *,
        session_id: str,
        source_position: int,
    ) -> tuple[str, ...]:
        """Private event history; not a student-facing endpoint."""

        with self._connection() as connection:
            self._session_row(connection, session_id)

            rows = connection.execute(
                """
                SELECT event_type
                FROM assistance_events
                WHERE session_id = ? AND source_position = ?
                ORDER BY event_id
                """,
                (session_id, source_position),
            ).fetchall()

        return tuple(row["event_type"] for row in rows)
