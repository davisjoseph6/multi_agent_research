"""Real SQLite exercise for fictional contact outbox; never sends email."""
from datetime import datetime, timedelta, timezone
import pytest

from src.prototype.research_v2_proposal import ProposedStudyError
from src.prototype.research_v2_reminder_outbox import SyntheticReminderOutbox


T0 = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def make(tmp_path):
    return SyntheticReminderOutbox(tmp_path / "contacts" / "fictional_contact_outbox.sqlite3")


def test_due_first_at_three_days_and_second_three_days_after_actual_delivery(tmp_path):
    q = make(tmp_path)
    q.register("SYN_CONTACT_F1", "learner1@example.test", locale="en", opted_in=True)
    q.pause("SYN_CONTACT_F1", T0)
    assert q.reserve_due(T0 + timedelta(days=2)) == ()
    first, = q.reserve_due(T0 + timedelta(days=3))
    assert q.reserve_due(T0 + timedelta(days=6)) == ()
    with pytest.raises(ProposedStudyError, match="premature"):
        q.deliver_preview(first, T0 + timedelta(days=2))
    assert q.deliver_preview(first, T0 + timedelta(days=3))["reminder"] == 1
    assert q.deliver_preview(first, T0 + timedelta(days=3))["replayed"]
    assert q.reserve_due(T0 + timedelta(days=5)) == ()
    second, = q.reserve_due(T0 + timedelta(days=6))
    assert second != first
    with pytest.raises(ProposedStudyError, match="premature"):
        q.deliver_preview(second, T0 + timedelta(days=5))
    result = q.deliver_preview(second, T0 + timedelta(days=6))
    assert result["preview_delivered"] and result["reminder"] == 2
    assert "email" not in result and "learner1@" not in str(result)
    assert q.reserve_due(T0 + timedelta(days=7)) == ()


def test_optout_resume_and_withdrawal_cancel_stale_claims(tmp_path):
    q = make(tmp_path)
    for suffix in ("A", "B", "C"):
        q.register("SYN_CONTACT_" + suffix, suffix.lower() + "@example.test",
                   locale="fr", opted_in=True)
        q.pause("SYN_CONTACT_" + suffix, T0)
    claims = q.reserve_due(T0 + timedelta(days=3))
    assert len(claims) == 3
    q.resume("SYN_CONTACT_A", T0 + timedelta(days=3))
    q.withdraw("SYN_CONTACT_B", T0 + timedelta(days=3))
    q.opt_out("SYN_CONTACT_C", T0 + timedelta(days=3))
    for claim in claims:
        with pytest.raises(ProposedStudyError, match="withheld"):
            q.deliver_preview(claim, T0 + timedelta(days=3))
    assert q.reserve_due(T0 + timedelta(days=6)) == ()


def test_new_pause_episode_does_not_reuse_old_claim(tmp_path):
    q = make(tmp_path)
    ref = "SYN_CONTACT_F1"
    q.register(ref, "example@example.test", locale="en", opted_in=True)
    q.pause(ref, T0)
    old, = q.reserve_due(T0 + timedelta(days=3))
    q.resume(ref, T0 + timedelta(days=4))
    q.pause(ref, T0 + timedelta(days=5))
    with pytest.raises(ProposedStudyError, match="withheld"):
        q.deliver_preview(old, T0 + timedelta(days=8))
    new, = q.reserve_due(T0 + timedelta(days=8))
    assert new != old
    assert q.deliver_preview(new, T0 + timedelta(days=8))["preview_delivered"]
    assert q.inspect_redacted(ref)["pause_episode"] == 2


def test_never_send_after_pause_deadline_or_to_real_domain(tmp_path):
    q = make(tmp_path)
    with pytest.raises(ProposedStudyError, match="synthetic"):
        q.register("SYN_CONTACT_F1", "real@example.org", locale="en", opted_in=True)
    q.register("SYN_CONTACT_F1", "learner1@example.test", locale="en", opted_in=True)
    q.pause("SYN_CONTACT_F1", T0)
    claim, = q.reserve_due(T0 + timedelta(days=3))
    with pytest.raises(ProposedStudyError, match="withheld"):
        q.deliver_preview(claim, T0 + timedelta(days=15))
    with pytest.raises(ProposedStudyError, match="expired"):
        q.resume("SYN_CONTACT_F1", T0 + timedelta(days=15))
    assert q.reserve_due(T0 + timedelta(days=15)) == ()


def test_transactionally_claims_only_once_from_two_handles(tmp_path):
    q1 = make(tmp_path)
    q2 = make(tmp_path)
    q1.register("SYN_CONTACT_F1", "f1@example.test", locale="fr", opted_in=True)
    q1.pause("SYN_CONTACT_F1", T0)
    first = q1.reserve_due(T0 + timedelta(days=3))
    second = q2.reserve_due(T0 + timedelta(days=3))
    assert len(first) == 1 and not second
    assert q2.deliver_preview(first[0], T0 + timedelta(days=3))["locale"] == "fr"
    assert q1.reserve_due(T0 + timedelta(days=6))


def test_inactive_and_not_opted_in_contacts_are_never_queued(tmp_path):
    q = make(tmp_path)
    q.register("SYN_CONTACT_F1", "f1@example.test", locale="en", opted_in=False)
    q.pause("SYN_CONTACT_F1", T0)
    assert q.reserve_due(T0 + timedelta(days=10)) == ()
    assert "email" not in q.inspect_redacted("SYN_CONTACT_F1")


def test_same_email_cannot_register_as_two_different_fictional_learners(tmp_path):
    q = make(tmp_path)
    q.register("SYN_CONTACT_F1", "demo@example.test", locale="en", opted_in=True)
    with pytest.raises(ProposedStudyError, match="already registered"):
        q.register("SYN_CONTACT_F2", "DEMO@example.test", locale="fr", opted_in=True)
    with pytest.raises(ProposedStudyError, match="already registered"):
        q.register("SYN_CONTACT_F1", "other@example.test", locale="en", opted_in=True)
