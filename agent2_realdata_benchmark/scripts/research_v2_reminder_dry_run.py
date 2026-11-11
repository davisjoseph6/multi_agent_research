"""Fictional bilingual reminder worker — memory-only transport, no network.

Offline isolated rehearsal. Real email recipients, HTTP connections and
SMTP/API credentials are never accepted. The preview store enforces .test
recipients, consent opt-in, two notices, 14-day pause and cancellation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.prototype.research_v2_reminder_outbox import SyntheticReminderOutbox
from src.prototype.research_v2_proposal import ProposedStudyError


START = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


class MemoryOnlyTransport:
    """Receives local test messages; intentionally has no send/network API."""

    def __init__(self):
        self.received = {}
    def capture(self, payload: dict) -> None:
        if (not payload.get("synthetic_only") or
                not payload["recipient"].lower().endswith(".test")):
            raise ProposedStudyError("nonfictional dispatch forbidden")
        key = payload["preview_idempotency_key"]
        if key in self.received and self.received[key] != payload:
            raise ProposedStudyError("idempotent preview payload changed")
        self.received[key] = dict(payload)


def drain_due(queue: SyntheticReminderOutbox, transport: MemoryOnlyTransport,
              now: datetime) -> dict:
    """Atomically reserve, capture in RAM and acknowledge due fake emails."""
    if type(transport) is not MemoryOnlyTransport:
        raise ProposedStudyError("only memory-only fictional transport is enabled")
    delivered = 0
    ids = queue.reserve_due(now)
    for queue_id in ids:
        payload = queue.preview_payload(queue_id, now)
        transport.capture(payload)
        # Successful in-memory capture stands in for a fake provider ACK.
        queue.deliver_preview(queue_id, now)
        delivered += 1
    return {
        "synthetic_only": True, "real_email_sent": False,
        "claims": len(ids), "captured_and_acknowledged": delivered,
    }


def main() -> None:
    with TemporaryDirectory(prefix="ijcai_v2_fictional_reminder_") as temp:
        q = SyntheticReminderOutbox(
            Path(temp) / "fictional_contact_outbox.sqlite3"
        )
        q.register("SYN_CONTACT_EN", "en@example.test",
                   locale="en", opted_in=True)
        q.register("SYN_CONTACT_FR", "fr@example.test",
                   locale="fr", opted_in=True)
        q.pause("SYN_CONTACT_EN", START)
        q.pause("SYN_CONTACT_FR", START)
        capture = MemoryOnlyTransport()
        timeline = [
            drain_due(q, capture, START + timedelta(days=day))
            for day in (0, 2, 3, 5, 6, 9)
        ]
        assert [x["captured_and_acknowledged"] for x in timeline] == [
            0, 0, 2, 0, 2, 0,
        ]
        assert len(capture.received) == 4
        print(json.dumps({
            "kind": "SYNTHETIC_BILINGUAL_REMINDER_DRY_RUN",
            "timeline": timeline, "captured_messages": 4,
            "languages": ["en", "fr"], "real_email_sent": False,
            "human_enrollment_authorized": False,
            "passed": True,
        }, indent=2))


if __name__ == "__main__":
    main()
