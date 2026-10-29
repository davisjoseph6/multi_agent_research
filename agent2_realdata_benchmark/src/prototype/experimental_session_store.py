"""Development-only, policy-gated quiz repository.

An immutable per-session policy controls offers.
Practice responses and assistance decisions are
recorded atomically.

Not authorized for real participant data.
"""

from __future__ import annotations

import math
import sqlite3

from dataclasses import dataclass
from uuid import uuid4

from src.prototype.assistance import DEMO_SUMMARY
from src.prototype.assistance_store import AssistanceConflict
from src.prototype.experimental_policies import (
    DEFAULT_DEMO_THRESHOLD,
    POLICY_MODES,
    choose_summary_offer,
)
from src.prototype.gated_assistance_store import (
    SQLiteFixedSummaryQuizRepository,
)
from src.prototype.item_bank import QuizItem


class ExperimentalConfigurationMismatch(ValueError):
    """Stored experiment configuration is inconsistent."""


@dataclass(frozen=True)
class RecordedPolicyDecision:
    source_position: int
    policy_mode: str
    offer_summary: bool
    mastery_belief: float
    reason: str


class SQLiteExperimentalQuizRepository(
    SQLiteFixedSummaryQuizRepository
):
    """Quiz and allocation stores share one SQLite file."""

    REPOSITORY_MODE = "experimental_demo_v1"

    def __init__(
        self,
        database_path,
        *,
        items: tuple[QuizItem, ...],
        bank_version: str,
        threshold: float = DEFAULT_DEMO_THRESHOLD,
    ) -> None:

        if (
            type(threshold) not in (float, int)
            or not math.isfinite(threshold)
            or not 0.0 <= threshold <= 1.0
        ):
            raise ValueError(
                "Invalid experimental threshold"
            )

        self._threshold = float(threshold)

        # Initialize the allocation store first,
        # using precisely this database file.
        with sqlite3.connect(database_path) as connection:
            exists = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'trial_allocations'
                """
            ).fetchone()

        if not exists:
            raise ExperimentalConfigurationMismatch(
                "Initialize the allocation store first"
            )

        super().__init__(
            database_path,
            items=items,
            bank_version=bank_version,
        )

        with self._write_transaction() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                experimental_configuration (
                    singleton INTEGER PRIMARY KEY
                        CHECK(singleton = 1),
                    threshold REAL NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                experimental_session_policies (
                    session_id TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL UNIQUE,
                    policy_mode TEXT NOT NULL
                        CHECK(policy_mode IN (
                            'control',
                            'fixed_summary',
                            'adaptive_threshold'
                        )),
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id),
                    FOREIGN KEY(participant_id)
                        REFERENCES trial_allocations(
                            participant_id
                        )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                experimental_policy_decisions (
                    session_id TEXT NOT NULL,
                    source_position INTEGER NOT NULL,
                    policy_mode TEXT NOT NULL,
                    mastery_belief REAL NOT NULL,
                    offer_summary INTEGER NOT NULL
                        CHECK(offer_summary IN (0, 1)),
                    reason TEXT NOT NULL,

                    PRIMARY KEY(
                        session_id,
                        source_position
                    ),

                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                )
                """
            )

            stored = connection.execute(
                """
                SELECT threshold
                FROM experimental_configuration
                WHERE singleton = 1
                """
            ).fetchone()

            if stored is None:

                count = connection.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]

                if count:
                    raise ExperimentalConfigurationMismatch(
                        "Existing sessions lack configuration"
                    )

                connection.execute(
                    """
                    INSERT INTO experimental_configuration
                    (singleton, threshold)
                    VALUES (1, ?)
                    """,
                    (self._threshold,),
                )

            elif stored["threshold"] != self._threshold:
                raise ExperimentalConfigurationMismatch(
                    "Stored threshold differs"
                )

    def create_session_for_participant(
        self,
        *,
        participant_id: str,
    ) -> str:
        """Bind a previously allocated synthetic participant.

        Repeated calls recover the same session.
        Both session creation and binding are atomic.
        """

        if (
            type(participant_id) is not str
            or not participant_id
        ):
            raise ValueError(
                "Invalid synthetic participant identifier"
            )

        with self._write_transaction() as connection:

            self._check_repository_mode(connection)

            assigned = connection.execute(
                """
                SELECT policy_mode
                FROM trial_allocations
                WHERE participant_id = ?
                """,
                (participant_id,),
            ).fetchone()

            if assigned is None:
                raise LookupError(
                    "Participant has no allocation"
                )

            policy_mode = assigned["policy_mode"]

            if policy_mode not in POLICY_MODES:
                raise ExperimentalConfigurationMismatch(
                    "Invalid allocated policy"
                )

            existing = connection.execute(
                """
                SELECT session_id, policy_mode
                FROM experimental_session_policies
                WHERE participant_id = ?
                """,
                (participant_id,),
            ).fetchone()

            if existing is not None:

                if existing["policy_mode"] != policy_mode:
                    raise ExperimentalConfigurationMismatch(
                        "Session policy differs from allocation"
                    )

                self._session_row(
                    connection,
                    existing["session_id"],
                )

                return existing["session_id"]

            session_id = uuid4().hex

            connection.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    bank_version,
                    bank_digest,
                    position
                )
                VALUES (?, ?, ?, 0)
                """,
                (
                    session_id,
                    self._version,
                    self._digest,
                ),
            )

            connection.execute(
                """
                INSERT INTO experimental_session_policies (
                    session_id,
                    participant_id,
                    policy_mode
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    participant_id,
                    policy_mode,
                ),
            )

        return session_id

    def create_session(self) -> str:
        """Disallow unallocated experimental sessions."""

        raise PermissionError(
            "An existing allocation is required"
        )

    def _policy_for_session(
        self,
        connection,
        session_id: str,
    ) -> str:

        self._session_row(
            connection,
            session_id,
        )

        row = connection.execute(
            """
            SELECT
                s.policy_mode AS session_mode,
                a.policy_mode AS allocation_mode

            FROM experimental_session_policies AS s

            JOIN trial_allocations AS a
              ON a.participant_id = s.participant_id

            WHERE s.session_id = ?
            """,
            (session_id,),
        ).fetchone()

        if (
            row is None
            or row["session_mode"] != row["allocation_mode"]
        ):
            raise ExperimentalConfigurationMismatch(
                "Missing or mismatched allocated policy"
            )

        return row["session_mode"]

    def read_policy(self, session_id: str) -> str:
        """Private backend read; not student-facing."""

        with self._connection() as connection:
            return self._policy_for_session(
                connection,
                session_id,
            )

    def _before_new_response(
        self,
        connection,
        *,
        session_id: str,
        position: int,
    ) -> None:

        self._policy_for_session(
            connection,
            session_id,
        )

        # Preserve the existing pending-offer gate.
        super()._before_new_response(
            connection,
            session_id=session_id,
            position=position,
        )

    def _after_new_response(
        self,
        connection,
        *,
        session_id: str,
        position: int,
        item: QuizItem,
    ) -> None:

        policy_mode = self._policy_for_session(
            connection,
            session_id,
        )

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

        # Include only committed practice responses
        # through the current decision boundary.
        rows = connection.execute(
            """
            SELECT correct
            FROM responses

            WHERE session_id = ?
              AND position <= ?
              AND kind = 'practice'
              AND concept_id = ?

            ORDER BY position
            """,
            (
                session_id,
                position,
                item.concept_id,
            ),
        ).fetchall()

        history = tuple(
            bool(row["correct"])
            for row in rows
        )

        decision = choose_summary_offer(
            policy_mode=policy_mode,
            eligible=True,
            practice_history=history,
            threshold=self._threshold,
        )

        connection.execute(
            """
            INSERT INTO experimental_policy_decisions (
                session_id,
                source_position,
                policy_mode,
                mastery_belief,
                offer_summary,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                position,
                policy_mode,
                decision.mastery_belief,
                int(decision.offer_summary),
                decision.reason,
            ),
        )

        if decision.offer_summary:

            # Reuse the established atomic offer
            # and event-ledger implementation.
            super()._after_new_response(
                connection,
                session_id=session_id,
                position=position,
                item=item,
            )

    def offer_after_practice(
        self,
        *,
        session_id: str,
        source_position: int,
    ):
        """Disallow bypassing the assigned policy."""

        raise AssistanceConflict(
            "Offers must originate from policy-gated submissions"
        )

    def read_policy_decisions(
        self,
        session_id: str,
    ) -> tuple[RecordedPolicyDecision, ...]:
        """Private, persisted decision audit."""

        with self._connection() as connection:

            self._policy_for_session(
                connection,
                session_id,
            )

            rows = connection.execute(
                """
                SELECT
                    source_position,
                    policy_mode,
                    mastery_belief,
                    offer_summary,
                    reason

                FROM experimental_policy_decisions

                WHERE session_id = ?

                ORDER BY source_position
                """,
                (session_id,),
            ).fetchall()

        return tuple(
            RecordedPolicyDecision(
                source_position=row["source_position"],
                policy_mode=row["policy_mode"],
                offer_summary=bool(row["offer_summary"]),
                mastery_belief=row["mastery_belief"],
                reason=row["reason"],
            )
            for row in rows
        )
