"""Isolated development-only participant allocation ledger.

Not connected to Flask, real students, or the existing
quiz database.

Experimental conditions are illustrative, not approved
RCT arms.
"""

from __future__ import annotations

import json
import secrets
import sqlite3

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.prototype.experimental_policies import POLICY_MODES


class TrialConfigurationMismatch(ValueError):
    """An allocation database cannot silently change design."""


@dataclass(frozen=True)
class TrialAssignment:
    participant_id: str
    policy_mode: str
    replayed: bool


class SQLiteTrialAllocationStore:
    """Atomic, replay-safe allocation for synthetic participants.

    A trusted backend supplies a stable, opaque enrollment
    request identifier.

    Do not expose allocation results in student-facing APIs.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        arms: tuple[str, ...] = (
            "control",
            "fixed_summary",
            "adaptive_threshold",
        ),
        block_sizes: tuple[int, ...] = (6, 9),
    ) -> None:

        if str(database_path) == ":memory:":
            raise ValueError(
                "A file-backed database is required"
            )

        if (
            type(arms) is not tuple
            or len(arms) < 2
            or any(type(a) is not str for a in arms)
            or len(set(arms)) != len(arms)
            or not set(arms).issubset(POLICY_MODES)
        ):
            raise ValueError(
                "Invalid candidate policy arms"
            )

        if (
            type(block_sizes) is not tuple
            or not block_sizes
            or any(
                type(n) is not int
                or n < len(arms)
                or n % len(arms) != 0
                for n in block_sizes
            )
        ):
            raise ValueError(
                "Block sizes must be positive arm multiples"
            )

        self._path = str(
            Path(database_path).expanduser()
        )

        self._arms = arms
        self._block_sizes = block_sizes

        self._configuration = json.dumps(
            {
                "version": "dev_trial_allocation_v1",
                "arms": arms,
                "block_sizes": block_sizes,
            },
            sort_keys=True,
        )

        self._initialize()

    @contextmanager
    def _connection(self):

        with sqlite3.connect(
            self._path,
            timeout=10.0,
        ) as connection:

            connection.row_factory = sqlite3.Row

            connection.execute(
                "PRAGMA busy_timeout=10000"
            )

            connection.execute(
                "PRAGMA foreign_keys=ON"
            )

            yield connection

    def _check_config(self, connection):

        row = connection.execute(
            """
            SELECT value
            FROM trial_allocation_config
            WHERE key='design'
            """
        ).fetchone()

        if (
            row is None
            or row["value"] != self._configuration
        ):
            raise TrialConfigurationMismatch(
                "Stored randomization design differs"
            )

    def _initialize(self):

        with self._connection() as connection:

            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                trial_allocation_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                trial_allocation_slots (
                    position INTEGER PRIMARY KEY
                        CHECK(position >= 0),
                    policy_mode TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                trial_allocations (
                    participant_id TEXT PRIMARY KEY,

                    enrollment_request_id TEXT
                        NOT NULL UNIQUE,

                    position INTEGER NOT NULL UNIQUE,

                    policy_mode TEXT NOT NULL,

                    assigned_at TEXT NOT NULL DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                    FOREIGN KEY(position)
                        REFERENCES trial_allocation_slots(position)
                )
                """
            )

            existing = connection.execute(
                """
                SELECT value
                FROM trial_allocation_config
                WHERE key='design'
                """
            ).fetchone()

            if existing is None:

                has_rows = connection.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM trial_allocations
                    )
                    """
                ).fetchone()[0]

                if has_rows:
                    raise TrialConfigurationMismatch(
                        "Unstamped allocations"
                    )

                connection.execute(
                    """
                    INSERT INTO trial_allocation_config
                    (key, value)
                    VALUES ('design', ?)
                    """,
                    (self._configuration,),
                )

            self._check_config(connection)

    def allocate(
        self,
        *,
        enrollment_request_id: str,
    ) -> TrialAssignment:
        """Assign one synthetic participant, atomically."""

        if (
            type(enrollment_request_id) is not str
            or not enrollment_request_id.strip()
            or len(enrollment_request_id) > 128
        ):
            raise ValueError(
                "Invalid enrollment request ID"
            )

        with self._connection() as connection:

            connection.execute("BEGIN IMMEDIATE")

            self._check_config(connection)

            existing = connection.execute(
                """
                SELECT participant_id, policy_mode
                FROM trial_allocations
                WHERE enrollment_request_id = ?
                """,
                (enrollment_request_id,),
            ).fetchone()

            if existing:

                return TrialAssignment(
                    existing["participant_id"],
                    existing["policy_mode"],
                    True,
                )

            position = connection.execute(
                """
                SELECT COUNT(*)
                FROM trial_allocations
                """
            ).fetchone()[0]

            slot = connection.execute(
                """
                SELECT policy_mode
                FROM trial_allocation_slots
                WHERE position = ?
                """,
                (position,),
            ).fetchone()

            if slot is None:

                size = secrets.choice(
                    self._block_sizes
                )

                planned = list(self._arms) * (
                    size // len(self._arms)
                )

                secrets.SystemRandom().shuffle(
                    planned
                )

                connection.executemany(
                    """
                    INSERT INTO trial_allocation_slots
                    (position, policy_mode)
                    VALUES (?, ?)
                    """,
                    (
                        (position + i, arm)
                        for i, arm in enumerate(planned)
                    ),
                )

                policy_mode = planned[0]

            else:

                policy_mode = slot["policy_mode"]

            participant_id = uuid4().hex

            connection.execute(
                """
                INSERT INTO trial_allocations (
                    participant_id,
                    enrollment_request_id,
                    position,
                    policy_mode
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    participant_id,
                    enrollment_request_id,
                    position,
                    policy_mode,
                ),
            )

        return TrialAssignment(
            participant_id,
            policy_mode,
            False,
        )

    def read_assignment(
        self,
        *,
        participant_id: str,
    ) -> TrialAssignment:
        """Trusted backend read; never expose publicly."""

        if (
            type(participant_id) is not str
            or not participant_id
        ):
            raise ValueError(
                "Invalid participant identifier"
            )

        with self._connection() as connection:

            self._check_config(connection)

            row = connection.execute(
                """
                SELECT participant_id, policy_mode
                FROM trial_allocations
                WHERE participant_id = ?
                """,
                (participant_id,),
            ).fetchone()

        if row is None:
            raise LookupError(
                "Unknown synthetic participant"
            )

        return TrialAssignment(
            row["participant_id"],
            row["policy_mode"],
            True,
        )
