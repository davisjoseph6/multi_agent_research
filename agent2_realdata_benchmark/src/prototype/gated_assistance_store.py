"""Atomic fixed-summary assistance gate for local demonstrations.

An eligible accepted practice response and its fixed-policy
offer are committed in one SQLite transaction.

This does not execute POMCP recommendations and is not
authorized for real participant studies.
"""

from __future__ import annotations

import sqlite3

from src.prototype.assistance import DEMO_SUMMARY
from src.prototype.assistance_store import (
    OfferSnapshot,
    SQLiteAssistanceRepository,
)
from src.prototype.item_bank import QuizItem
from src.prototype.sqlite_store import ResponseConflict


class SQLiteFixedSummaryQuizRepository(
    SQLiteAssistanceRepository
):
    """An explicitly enabled fixed-summary demonstration policy."""

    def _before_new_response(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        position: int,
    ) -> None:
        """Reject new answers while an offer remains unresolved."""

        unresolved = connection.execute(
            """
            SELECT 1
            FROM assistance_offers
            WHERE session_id = ?
              AND target_position = ?
              AND status IN ('offered', 'accepted')
            LIMIT 1
            """,
            (session_id, position),
        ).fetchone()

        if unresolved is not None:
            raise ResponseConflict(
                "Assistance decision or delivery is pending"
            )

    def _after_new_response(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        position: int,
        item: QuizItem,
    ) -> None:
        """Atomically create an eligible fixed-policy offer."""

        target_position = position + 1

        if target_position >= len(self._items):
            return

        target = self._items[target_position]

        eligible = (
            item.kind == "practice"
            and target.kind == "practice"
            and item.concept_id == DEMO_SUMMARY.concept_id
            and target.concept_id == DEMO_SUMMARY.concept_id
        )

        if not eligible:
            return

        connection.execute(
            """
            INSERT INTO assistance_offers (
                session_id,
                source_position,
                target_position,
                resource_id,
                status
            )
            VALUES (?, ?, ?, ?, 'offered')
            """,
            (
                session_id,
                position,
                target_position,
                DEMO_SUMMARY.resource_id,
            ),
        )

        self._event(
            connection,
            session_id,
            position,
            "proposed",
        )

        self._event(
            connection,
            session_id,
            position,
            "offered",
        )

    def current_offer(
        self,
        session_id: str,
    ) -> OfferSnapshot | None:
        """Read the offer associated with the current question.

        This is a development read model. The authoritative
        submission gate remains inside the write transaction.
        """

        with self._connection() as connection:
            connection.execute("BEGIN")

            try:
                state = self._session_row(
                    connection,
                    session_id,
                )

                row = connection.execute(
                    """
                    SELECT *
                    FROM assistance_offers
                    WHERE session_id = ?
                      AND target_position = ?
                    """,
                    (session_id, state["position"]),
                ).fetchone()

            finally:
                connection.rollback()

        if row is None:
            return None

        return self._snapshot(row)
