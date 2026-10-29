"""Synthetic invitation-enrollment integrity tests."""

import sqlite3

from concurrent.futures import ThreadPoolExecutor

import pytest

from src.prototype.invitation_enrollment import (
    InvalidInvitation,
    SQLiteInvitationEnrollmentStore,
)


@pytest.fixture
def store(tmp_path):

    return SQLiteInvitationEnrollmentStore(
        tmp_path / "invitation_demo.sqlite3",
        block_sizes=(6,),
    )


def test_invitation_is_high_entropy(store):

    first = store.issue_invitation()
    second = store.issue_invitation()

    assert first.startswith("inv1_")
    assert len(first) == 69

    assert first != second


def test_plaintext_token_is_not_stored(
    store,
    tmp_path,
):

    token = store.issue_invitation()

    database = (
        tmp_path / "invitation_demo.sqlite3"
    )

    with sqlite3.connect(database) as db:
        records = db.execute(
            """
            SELECT token_digest
            FROM trial_invitations
            """
        ).fetchall()

    assert len(records) == 1
    assert records[0][0] != token
    assert token not in str(records)


def test_repeated_redemption_recovers_session(store):

    token = store.issue_invitation()

    first = store.redeem_invitation(token)
    second = store.redeem_invitation(token)

    assert first.session_id == second.session_id

    assert first.replayed is False
    assert second.replayed is True


def test_unknown_invitation_does_not_allocate(
    store,
    tmp_path,
):

    unknown = "inv1_" + "f" * 64

    with pytest.raises(InvalidInvitation):
        store.redeem_invitation(unknown)

    with sqlite3.connect(
        tmp_path / "invitation_demo.sqlite3"
    ) as db:

        count = db.execute(
            """
            SELECT COUNT(*)
            FROM trial_allocations
            """
        ).fetchone()[0]

    assert count == 0


@pytest.mark.parametrize("invalid", [
    None,
    "",
    "test",
    "inv1_short",
    "inv1_" + "z" * 64,
    False,
    "inv1_" + "a" * 65,
])
def test_malformed_invitations_rejected(
    store,
    invalid,
):

    with pytest.raises(InvalidInvitation):
        store.redeem_invitation(invalid)


def test_distinct_invitations_get_distinct_sessions(store):

    first = store.redeem_invitation(
        store.issue_invitation()
    )

    second = store.redeem_invitation(
        store.issue_invitation()
    )

    assert first.session_id != second.session_id


def test_restart_preserves_invitation_binding(
    store,
    tmp_path,
):

    token = store.issue_invitation()
    first = store.redeem_invitation(token)

    restarted = SQLiteInvitationEnrollmentStore(
        tmp_path / "invitation_demo.sqlite3",
        block_sizes=(6,),
    )

    recovered = restarted.redeem_invitation(token)

    assert recovered.replayed is True
    assert recovered.session_id == first.session_id


def test_concurrent_redeem_returns_same_session(store):

    token = store.issue_invitation()

    with ThreadPoolExecutor(
        max_workers=6
    ) as pool:

        results = list(
            pool.map(
                store.redeem_invitation,
                [token] * 10,
            )
        )

    assert len({
        result.session_id
        for result in results
    }) == 1


def test_invalid_token_cannot_reuse_valid_session(store):

    valid_token = store.issue_invitation()

    valid = store.redeem_invitation(
        valid_token
    )

    forged_token = (
        valid_token[:-1]
        + (
            "0"
            if valid_token[-1] != "0"
            else "1"
        )
    )

    with pytest.raises(InvalidInvitation):
        store.redeem_invitation(forged_token)

    assert store.redeem_invitation(
        valid_token
    ).session_id == valid.session_id
