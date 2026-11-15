"""Synthetic-only supervisor GDPR intake, strictly in the documented order.

No network email provider, real registration or institutional authorization.
Consent and eligible screening drafts are held in memory, NOT database,
until registration. Accepted legal wording is pinned to v1.0.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Mapping

from .supervisor_consent_texts import (
    CONSENT_VERSION, DEBRIEF, DELETE_CONFIRMATION, DUPLICATE,
    INELIGIBLE, KEEP_CONFIRMATION, REGISTERED, TOKEN_BODY, TOKEN_SUBJECT,
)
from .supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError, iso,
)


class SyntheticConsentFlow:
    def __init__(self, store: SupervisorSyntheticStore, *,
                 programs: tuple[str, ...] = ("Synthetic classroom demonstration",)):
        if not isinstance(store, SupervisorSyntheticStore):
            raise TypeError("supervisor fictional store required")
        if not programs or any(not isinstance(x,str) or not x.strip() for x in programs):
            raise SyntheticStudyError("explicit program options required")
        self.store=store
        self.programs=tuple(programs)
        self.drafts={}
        self.private_mail_preview=[]
        self.identities={}
        self.closed=set()

    @staticmethod
    def _fixture(fixture: str) -> None:
        if fixture not in ("F1","F2","F3"):
            raise SyntheticStudyError("fictional F1/F2/F3 fixture required")

    def start_consent(self, fixture: str, *,
                      checks: list[bool], optional: bool,
                      language: str, at: datetime) -> dict:
        self._fixture(fixture)
        if fixture in self.identities or fixture in self.closed:
            raise SyntheticStudyError("already registered or excluded fictional fixture")
        if (type(checks) is not list or len(checks)!=6
                or any(type(x) is not bool for x in checks)
                or type(optional) is not bool
                or language not in ("en","fr")):
            raise SyntheticStudyError("six explicit checkbox values required")
        if not all(checks):
            raise SyntheticStudyError("all six required consent statements must be accepted")
        self.drafts[fixture]=dict(
            consent_version=CONSENT_VERSION,
            consent_lang=language,consent_at=at,
            open_data_consent=optional,screening_answers=None,
            screening_score=None,
        )
        return {"next":"screening","consent_version":CONSENT_VERSION,
                "synthetic_only":True}

    def declare_economics_course(self, fixture: str) -> dict:
        """No screening log or persistence: course-link stops before screening."""
        self._fixture(fixture)
        if fixture in self.identities:
            raise SyntheticStudyError("already registered")
        self.drafts.pop(fixture,None)
        self.closed.add(fixture)
        return {"eligible":False,"message":INELIGIBLE,"synthetic_only":True}

    def screen(self, fixture: str, *, answers: Mapping[str,str], at: datetime) -> dict:
        self._fixture(fixture)
        draft=self.drafts.get(fixture)
        if not draft or draft["screening_answers"] is not None:
            raise SyntheticStudyError("consent is required before a single screening")
        if type(answers) is not dict:
            raise SyntheticStudyError("screening answer map required")
        eligible,score=self.store.bank.eligible(
            econ_course=False,screening_answers=answers,
        )
        if not eligible:
            self.store.log_screening_exclusion(score,at=at)
            self.drafts.pop(fixture,None)
            self.closed.add(fixture)
            return {"eligible":False,"message":INELIGIBLE,"synthetic_only":True}
        draft["screening_answers"]=dict(answers)
        draft["screening_score"]=score
        return {"eligible":True,"next":"registration","synthetic_only":True}

    def register(self, fixture: str, *,
                 email: str, age: int, program: str, at: datetime) -> dict:
        self._fixture(fixture)
        draft=self.drafts.get(fixture)
        if not draft or draft["screening_answers"] is None:
            raise SyntheticStudyError("complete consent and screening before registration")
        if type(age) is not int or not 18 <= age <= 99:
            raise SyntheticStudyError("age must be 18..99")
        if program not in self.programs:
            raise SyntheticStudyError("choose a listed academic program")
        if not isinstance(email,str) or not re.fullmatch(
            r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.test", email,re.IGNORECASE
        ):
            raise SyntheticStudyError("only reserved fictional .test emails allowed")
        result=self.store.register(
            contact_email=email, econ_course=False,
            screening_answers=draft["screening_answers"],
            consent_version=CONSENT_VERSION,consent_given=True,
            consent_lang=draft["consent_lang"],
            open_data_consent=draft["open_data_consent"],
            consent_at=draft["consent_at"],
            age=age,program=program,at=at,
        )
        if not result["eligible"]:
            raise SyntheticStudyError("screening changed after consent")
        ref=result["fictional_learner_id"]
        token=result["fictional_private_token"]
        self.identities[fixture]=(ref,token)
        # Fake delivery is retained in RAM and NEVER exposed in browser JSON.
        self.private_mail_preview.append({
            "type":"invitation","recipient":email,
            "subject":TOKEN_SUBJECT,"body":TOKEN_BODY,
            "fictional_link_token":token,"synthetic_only":True,
            "real_email_sent":False,
        })
        self.drafts.pop(fixture,None)
        return {"registered":True,"message":REGISTERED,
                "synthetic_only":True,"human_enrollment_authorized":False,
                "real_email_sent":False}

    def withdraw(self, fixture: str, *, delete: bool, at: datetime,
                 channel: str = "website") -> dict:
        self._fixture(fixture)
        if fixture not in self.identities:
            raise SyntheticStudyError("fictional participant not registered")
        ref,token=self.identities[fixture]
        confirmation=DELETE_CONFIRMATION if delete else KEEP_CONFIRMATION
        # A no-network preview is captured before erasure; the live sender
        # is deliberately withheld until institutional deployment approval.
        with self.store._tx() as db:
            row=db.execute(
                "SELECT email FROM pii.contacts WHERE learner_id=?",(ref,)
            ).fetchone()
        if row is None or not row["email"].lower().endswith(".test"):
            raise SyntheticStudyError("fictional email confirmation unavailable")
        self.private_mail_preview.append({
            "type":"withdrawal","recipient":row["email"],
            "body":confirmation,"synthetic_only":True,
            "real_email_sent":False,
        })
        try:
            result=self.store.withdraw(
                ref,token,delete=delete,channel=channel,at=at)
        except BaseException:
            self.private_mail_preview.pop()
            raise
        del self.identities[fixture]
        self.closed.add(fixture)
        return {"withdrawn":True,"data_deleted":delete,
                "message":confirmation,"synthetic_only":True,
                "real_email_sent":False}

    def completed_debrief(self, fixture: str) -> dict:
        self._fixture(fixture)
        ref,token=self.identities[fixture]
        with self.store._tx() as db:
            self.store._authenticated(db,ref,token)
            row=db.execute(
                "SELECT status FROM participants WHERE learner_id=?",(ref,)
            ).fetchone()
        if row["status"]!="completed":
            raise SyntheticStudyError("complete Session 3 first")
        return {"kind":"debrief","text":DEBRIEF,
                "synthetic_only":True}

    def privately_export_points(self) -> list[dict]:
        return self.store.points_export()
