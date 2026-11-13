"""Local-only, read-only invitation lifecycle inspection.

This utility never prints bearer URLs, token hashes or email addresses,
never sends email and never alters the experiment. Run via the existing
restricted service account and protected staging environment.

The external Caddy Basic Auth status cannot be inferred from this database.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
import json

from scripts.supervisor_vps_admin import load
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import iso


def inspect(intake: OperationalIntake, recipient: str, *, at: datetime) -> dict:
    if type(recipient) is not str or "@" not in recipient:
        raise ValueError("a recipient email must be supplied privately")
    now=iso(at)
    with intake.store._tx() as db:
        row=db.execute(
            "SELECT token_hash,state,expires_at,learner_id "
            "FROM pii.invitations WHERE email=? COLLATE NOCASE",
            (recipient.strip(),),
        ).fetchone()
        if row is None:
            return {
                "record_found":False,
                "can_register_before_expiry":False,
                "registered_link_reusable":False,
                "no_token_or_recipient_printed":True,
            }
        registered=row["state"]=="registered"
        can_claim=not registered and row["expires_at"]>=now
        can_resume=False
        learner_status=None
        if registered:
            record=db.execute(
                "SELECT p.status AS participant_status,c.token_hash AS contact_token "
                "FROM participants p LEFT JOIN pii.contacts c "
                "ON p.learner_id=c.learner_id WHERE p.learner_id=?",
                (row["learner_id"],),
            ).fetchone()
            if record is not None:
                learner_status=record["participant_status"]
                can_resume=(
                    record["contact_token"]==row["token_hash"]
                    and learner_status in ("active","completed")
                )
        return {
            "record_found":True,
            "stage":row["state"],
            "initial_registration_expires_utc":row["expires_at"],
            "can_register_before_expiry":can_claim,
            "registered_link_reusable":can_resume,
            "registered_ignores_original_registration_expiry":registered,
            "participant_status":learner_status,
            "cookie_lifetime_days":14,
            "caddy_login_must_be_checked_separately":True,
            "no_token_or_recipient_printed":True,
        }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",required=True,
                        help="prompt privately for a single recipient email")
    args=parser.parse_args()
    assert args.check
    intake,_=load()
    recipient=getpass("Recipient email to inspect (hidden; not logged): ")
    result=inspect(intake,recipient,at=datetime.now(timezone.utc))
    print(json.dumps(result,indent=2,sort_keys=True))
    print("Note: does not confirm Caddy credentials, token possession, or "
          "a particular browser's cookie. No token has been revealed.")


if __name__=="__main__":
    main()
