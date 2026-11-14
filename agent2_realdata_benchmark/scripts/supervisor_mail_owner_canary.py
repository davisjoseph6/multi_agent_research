"""Local delegated-OAuth mailbox *self*-delivery canary, never a study invite.

Exactly one harmless test message is addressed to the same verified mailbox
whose owner completed local OAuth. It cannot issue links, send recruitment
material, or enable LIVE. A durable exclusive receipt prevents automatic
retry after an uncertain provider response. No tokens are printed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import stat

from src.prototype.supervisor_mail_providers import (
    DelegatedOAuthSender, EncryptedRefreshVault, MailConfigurationError,
)
from src.prototype.supervisor_recruitment import canonical_email


def one_shot_self_canary(sender, *, receipt_file: Path) -> dict:
    """Reserve once BEFORE a real provider call; no retry, even after failure."""
    path = Path(receipt_file)
    if (not path.is_absolute() or path.is_symlink() or path.exists()
            or not path.parent.is_dir() or path.parent.is_symlink()
            or stat.S_IMODE(path.parent.stat().st_mode) != 0o700):
        raise MailConfigurationError("fresh absolute receipt under a 0700 directory required")
    if sender.provider not in ("gmail_delegated", "graph_delegated"):
        raise MailConfigurationError("only owner-consented delegated OAuth is supported")
    recipient = canonical_email(sender.sender)
    token = secrets.token_hex(8)
    details = {
        "purpose": "NON_RESEARCH_OWNER_EMAIL_CANARY_ONLY",
        "provider": sender.provider,
        "attempt_id": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "uncertain",
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(details, output, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    # A caller cannot accidentally resend the same attempt: the file exists.
    try:
        sender.send(
            to=recipient,
            subject="IJCAI engineering mailbox connectivity test (no study invitation)",
            body=("This is a one-time mailbox owner delivery test. "
                  "It contains no questionnaire, private token, learner data "
                  "or authorization to recruit real participants. "
                  "You may disregard this message.\n"
                  "Test reference: " + token + "\n"),
        )
    except Exception:
        # The uncertain receipt deliberately remains: reconciliation is manual.
        raise
    details["state"] = "provider_accepted_not_inbox_confirmed"
    temp = path.with_name(path.name + "." + token + ".tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(details, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return {"canary": "provider_accepted", "inbox_delivery_verified": False,
            "study_mail_enabled": False, "human_enrollment_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("gmail_delegated", "graph_delegated"),
                        required=True)
    parser.add_argument("--sender", required=True,
                        help="actual authorized mailbox, not merely login alias")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--tenant", default=None)
    parser.add_argument("--client-secret-file", default=None)
    parser.add_argument("--vault-dir", type=Path, required=True)
    parser.add_argument("--vault-key-file", type=Path, required=True)
    parser.add_argument("--receipt-file", type=Path, required=True)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirm-own-mailbox", action="store_true")
    args = parser.parse_args()
    # Always reject a Microsoft Gmail login alias, which does not establish
    # an Outlook mailbox, even in dry-run mode.
    vault = EncryptedRefreshVault(args.vault_dir, args.vault_key_file)
    sender = DelegatedOAuthSender(
        provider=args.provider, sender=args.sender, client_id=args.client_id,
        client_secret_path=args.client_secret_file, vault=vault,
        tenant=args.tenant,
    )
    with vault.exclusive():
        vault.load(args.provider, sender.sender)
    if not args.send:
        print(json.dumps({
            "state": "OAUTH_OWNER_VAULT_PREFLIGHT_PASSED",
            "mail_sent": False, "live_enrollment_authorized": False,
        }, sort_keys=True))
        return
    if not args.confirm_own_mailbox:
        parser.error("--send requires --confirm-own-mailbox; you cannot use colleagues' credentials")
    try:
        result = one_shot_self_canary(sender, receipt_file=args.receipt_file)
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        print(json.dumps({
            "state": "CANARY_OUTCOME_UNCERTAIN_DO_NOT_RESEND",
            "error_class": type(exc).__name__, "enrollment_authorized": False,
        }, sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
