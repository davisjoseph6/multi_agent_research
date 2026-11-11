"""Bilingual memory-only outbox capture, opt-out and retry tests."""
from datetime import timedelta
import pytest

from scripts.research_v2_reminder_dry_run import (
    START, MemoryOnlyTransport, drain_due,
)
from src.prototype.research_v2_proposal import ProposedStudyError
from src.prototype.research_v2_reminder_outbox import SyntheticReminderOutbox


def make_queue(tmp_path):
    return SyntheticReminderOutbox(
        tmp_path / "fictional_contact_outbox.sqlite3"
    )


def test_english_french_content_and_exact_three_day_spacing(tmp_path):
    q = make_queue(tmp_path)
    q.register("SYN_CONTACT_EN", "en@example.test",
               locale="en", opted_in=True)
    q.register("SYN_CONTACT_FR", "fr@example.test",
               locale="fr", opted_in=True)
    q.pause("SYN_CONTACT_EN", START)
    q.pause("SYN_CONTACT_FR", START)
    t = MemoryOnlyTransport()
    assert drain_due(q, t, START + timedelta(days=2))[
        "captured_and_acknowledged"] == 0
    assert drain_due(q, t, START + timedelta(days=3))[
        "captured_and_acknowledged"] == 2
    assert drain_due(q, t, START + timedelta(days=5))["claims"] == 0
    assert drain_due(q, t, START + timedelta(days=6))[
        "captured_and_acknowledged"] == 2
    assert drain_due(q, t, START + timedelta(days=9))["claims"] == 0
    assert len(t.received) == 4
    locales = {x["locale"] for x in t.received.values()}
    assert locales == {"en", "fr"}
    assert all(x["recipient"].endswith(".test") for x in t.received.values())
    assert all("reminder" in x["preview_idempotency_key"].lower()
               for x in t.received.values())
    assert not any("arm" in x for x in t.received.values())


def test_withdrawal_optout_and_completion_prohibit_dispatch(tmp_path):
    q = make_queue(tmp_path)
    for suffix in ("A", "B", "C"):
        q.register("SYN_CONTACT_" + suffix, suffix + "@example.test",
                   locale="en", opted_in=True)
        q.pause("SYN_CONTACT_" + suffix, START)
    at = START + timedelta(days=3)
    claims = q.reserve_due(at)
    assert len(claims) == 3
    q.withdraw("SYN_CONTACT_A", at)
    q.opt_out("SYN_CONTACT_B", at)
    q.complete("SYN_CONTACT_C", at)
    for queue_id in claims:
        with pytest.raises(ProposedStudyError, match="inactive"):
            q.preview_payload(queue_id, at)
    assert drain_due(q, MemoryOnlyTransport(), START + timedelta(days=6))[
        "claims"] == 0


def test_expired_lease_requires_reacquire_same_preview_idempotency_key(tmp_path):
    q = make_queue(tmp_path)
    q.register("SYN_CONTACT_EN", "en@example.test", locale="en", opted_in=True)
    q.pause("SYN_CONTACT_EN", START)
    at = START + timedelta(days=3)
    first, = q.reserve_due(at)
    with pytest.raises(ProposedStudyError, match="lease expired"):
        q.preview_payload(first, at + timedelta(minutes=31))
    again, = q.reserve_due(at + timedelta(minutes=31))
    assert again == first
    payload = q.preview_payload(again, at + timedelta(minutes=31))
    assert payload["preview_idempotency_key"] == f"SYN_V2_REMINDER_{first}"
    t = MemoryOnlyTransport()
    t.capture(payload)
    q.deliver_preview(again, at + timedelta(minutes=31))
    assert len(t.received) == 1


def test_no_real_transport_or_recipient_accepted(tmp_path):
    q = make_queue(tmp_path)
    with pytest.raises(ProposedStudyError, match="synthetic"):
        q.register("SYN_CONTACT_BAD", "real@university.edu",
                   locale="en", opted_in=True)
    q.register("SYN_CONTACT_OK", "ok@example.test",
               locale="en", opted_in=True)
    q.pause("SYN_CONTACT_OK", START)
    with pytest.raises(ProposedStudyError, match="memory-only"):
        drain_due(q, object(), START + timedelta(days=3))
    t = MemoryOnlyTransport()
    with pytest.raises(ProposedStudyError, match="nonfictional"):
        t.capture({"synthetic_only":True,"recipient":"real@example.org",
                   "preview_idempotency_key":"fake"})
    assert drain_due(q, t, START + timedelta(days=3))[
        "captured_and_acknowledged"] == 1
