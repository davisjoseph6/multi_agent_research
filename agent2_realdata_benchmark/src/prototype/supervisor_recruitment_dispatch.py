"""Verified-LIVE bulk invitation dispatch with private capability files.

Admin staff can send to selected or all pre-approved candidates. One issued
student credential per address. No re-sending after Graph's uncertain outcome:
an authorized operator must reconcile the message in Outlook Sent Items.
This is not mounted by the old staging participant portal.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import stat

from scripts.supervisor_vps_admin import (
    write_private, read_retryable_invitation,
)
from .supervisor_operational_intake import OperationalIntake
from .supervisor_recruitment import (
    RecruitmentLedger,RecruitmentError,ADMIN_EMAILS,utc
)


class InvitationDispatcher:
    def __init__(self, *, intake: OperationalIntake,
                 ledger: RecruitmentLedger, sender,
                 hostname: str, live_verified: bool = False,
                 allow_test_examples: bool = False):
        if live_verified is not True:
            raise RecruitmentError("signed institutional LIVE release required")
        if not isinstance(intake,OperationalIntake) or not isinstance(ledger,RecruitmentLedger):
            raise TypeError("private recruitment ledger and operational study required")
        if type(hostname) is not str or "/" in hostname or "demo" in hostname or "." not in hostname:
            raise RecruitmentError("approved non-demo canonical study host required")
        if not hasattr(sender,"send") or not callable(sender.send):
            raise TypeError("approved Microsoft Graph sender required")
        if type(allow_test_examples) is not bool:
            raise TypeError("fixture restriction must be explicit")
        self.intake=intake
        self.ledger=ledger
        self.sender=sender
        self.hostname=hostname
        self.allow_test_examples=allow_test_examples
        self.root=ledger.file.parent
        if self.root != intake.store.folder:
            raise RecruitmentError("private candidate and contact databases must share state root")
        if self.root.stat().st_mode & 0o077:
            raise RecruitmentError("state directory must be owner-only")

    def dispatch(self, *, actor: str, at: datetime,
                 ids: list[int] | None = None, all_approved: bool = False):
        if actor not in ADMIN_EMAILS:
            raise RecruitmentError("only approved researchers may issue links")
        candidates=self.ledger.selected_for_invitation(
            ids=ids,all_approved=all_approved)
        result=dict(selected=len(candidates),accepted=0,
                    uncertain=0,rejected=0,pii_exposed=False,
                    delivery_not_guaranteed=True)
        for candidate in candidates:
            cid=candidate["candidate_id"]
            email=candidate["email"]
            if not candidate["approved_for_invitation"] or candidate["invitation_status"]=="accepted":
                result["rejected"]+=1
                continue
            if candidate["invitation_status"] not in ("potential","prepared"):
                result["rejected"]+=1
                continue
            private=self.root/f"candidate-invite-{cid:06d}.txt"
            newly_generated=None
            if private.exists():
                # Original capability is verified against the independently
                # protected contacts DB. Never expose its secret to the API.
                link=read_retryable_invitation(
                    path=private,root=self.root,host=self.hostname,
                    email=email,intake=self.intake,at=at,
                )
            else:
                token=self.intake.issue(
                    email,at=at,allow_example=self.allow_test_examples
                )
                newly_generated=token
                link=f"https://{self.hostname}/study/#invite={token}"
                try:
                    write_private(private,link)
                except BaseException:
                    self.intake.cancel_unclaimed_private_file_failure(token)
                    raise
            try:
                self.ledger.mark_prepared(
                    candidate_id=cid,actor=actor,at=at)
                self.ledger.reserve_mail(
                    candidate_id=cid,actor=actor,at=at)
            except BaseException:
                # Do not revoke an existing invitation that may already have
                # reached someone. The protected file and ledger can be audited.
                raise
            subject=("Invitation privée à l'étude d'apprentissage" if
                     candidate["language"]=="fr" else
                     "Private invitation to the adaptive learning study")
            body=(
                "Votre lien privé d'accès à l'étude :\n" if candidate["language"]=="fr"
                else "Your private study invitation link:\n"
            )+link+(
                "\n\nVeuillez lire les informations et donner votre consentement avant de commencer."
                if candidate["language"]=="fr" else
                "\n\nPlease review the participant information and provide consent before beginning."
            )
            try:
                # A mailbox choice is authorized by a separately signed
                # sender policy, never by the caller's researcher role.
                provider=(self.sender.for_actor(actor)
                          if hasattr(self.sender,"for_actor") else self.sender)
                if hasattr(provider,"journal"):
                    provider.send(to=email,subject=subject,body=body,
                                  delivery_key=f"study-invite:{cid}")
                else:
                    provider.send(to=email,subject=subject,body=body)
            except Exception:
                self.ledger.finish_mail(
                    candidate_id=cid,accepted=False,actor=actor,at=at)
                result["uncertain"]+=1
                # Never retry automatically: Microsoft Graph's response can
                # be lost even if Exchange accepted the message.
                continue
            self.ledger.finish_mail(
                candidate_id=cid,accepted=True,actor=actor,at=at)
            result["accepted"]+=1
        return result
