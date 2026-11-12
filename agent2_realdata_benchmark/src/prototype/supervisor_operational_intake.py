"""Persistent invitation-only intake for the supervisor's parallel RCT.

This module is usable in a TEST deployment with reserved *.example addresses.
Human enrollment is a separate institutional release decision, not a property
of a database schema or the presence of a TLS certificate.

Invitations live in the *contacts* SQLite attachment, not the deidentified
research tables. No participant may choose an arm, bypass screening, or create
their own invitation. Only the offline staff CLI may issue invitations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
import secrets

from .supervisor_consent_texts import CONSENT_VERSION, required_for_recipient
from .supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError, dump, iso,
)

_ALLOWED = re.compile(r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{40,256}\Z")


class OperationalIntake:
    def __init__(self, store: SupervisorSyntheticStore, *,
                 programs: tuple[str, ...]):
        if not isinstance(store, SupervisorSyntheticStore) or not store.operational:
            raise TypeError("separately configured operational database required")
        if not programs or any(type(v) is not str or not v.strip()
                               for v in programs):
            raise ValueError("non-empty institutionally reviewed program list required")
        self.store = store
        self.programs = tuple(programs)

    @staticmethod
    def digest(token: str) -> str:
        if not isinstance(token,str) or not _TOKEN.fullmatch(token):
            raise SyntheticStudyError("invalid invitation credential")
        return sha256(token.encode("ascii")).hexdigest()

    def issue(self, email: str, *, at: datetime, validity_days: int = 21,
              allow_example: bool = False) -> str:
        if (type(email) is not str or len(email)>254
                or not _ALLOWED.fullmatch(email)):
            raise SyntheticStudyError("invalid invitation recipient")
        if email.lower().endswith(".test"):
            raise SyntheticStudyError("fictional .test contacts refused")
        if allow_example:
            if not email.lower().endswith(".example"):
                raise SyntheticStudyError("TEST sender requires reserved .example")
        elif email.lower().endswith((".example",".invalid",".localhost")):
            raise SyntheticStudyError("non-deliverable production email")
        if type(validity_days) is not int or not 1 <= validity_days <= 30:
            raise SyntheticStudyError("invitation validity must be 1..30 days")
        token=secrets.token_urlsafe(40)
        digest=self.digest(token)
        until=iso(at+timedelta(days=validity_days))
        with self.store._tx() as db:
            if db.execute(
                "SELECT closed_at FROM collection_status WHERE one=1"
            ).fetchone()["closed_at"] is not None:
                raise SyntheticStudyError("collection has closed")
            if db.execute(
                "SELECT 1 FROM pii.contacts WHERE email=? COLLATE NOCASE",
                (email,),
            ).fetchone():
                raise SyntheticStudyError("contact already registered")
            if db.execute(
                "SELECT 1 FROM pii.invitations WHERE email=? COLLATE NOCASE",
                (email,),
            ).fetchone():
                raise SyntheticStudyError("invitation already issued")
            db.execute(
                "INSERT INTO pii.invitations(token_hash,email,expires_at,state)"
                " VALUES(?,?,?,'invited')",(digest,email,until),
            )
        return token

    def rotate_registered_test(self, email: str, *, new_token: str,
                               at: datetime) -> str:
        """Rotate an existing registered .example fixture without losing progress.

        Offline/staging administrative operation, never a participant route.
        The caller writes the new capability into a protected file *before*
        invoking this transaction. Existing cookies and shared invitation
        URLs immediately become invalid after the successful commit.
        """
        if (type(email) is not str or not _ALLOWED.fullmatch(email)
                or not email.lower().endswith(".example")):
            raise SyntheticStudyError("staging rotation requires a reserved .example address")
        new_hash = self.digest(new_token)
        with self.store._tx() as db:
            record = db.execute(
                "SELECT token_hash,learner_id FROM pii.invitations "
                "WHERE email=? COLLATE NOCASE AND state='registered'",
                (email,),
            ).fetchone()
            if record is None or not record["learner_id"]:
                raise SyntheticStudyError("registered fictional invitation required")
            old_hash = record["token_hash"]
            ref = record["learner_id"]
            active = db.execute(
                "SELECT status FROM participants WHERE learner_id=?",
                (ref,),
            ).fetchone()
            contact = db.execute(
                "SELECT token_hash FROM pii.contacts WHERE learner_id=? "
                "AND email=? COLLATE NOCASE",
                (ref, email),
            ).fetchone()
            if (active is None or active["status"] != "active"
                    or contact is None or contact["token_hash"] != old_hash
                    or new_hash == old_hash):
                raise SyntheticStudyError("registered study identity not eligible for rotation")
            if db.execute(
                "SELECT 1 FROM pii.invitations WHERE token_hash=?",
                (new_hash,),
            ).fetchone():
                raise SyntheticStudyError("replacement credential already exists")
            changed = db.execute(
                "UPDATE pii.contacts SET token_hash=?,token_created_at=? "
                "WHERE learner_id=? AND token_hash=?",
                (new_hash, iso(at), ref, old_hash),
            )
            if changed.rowcount != 1:
                raise SyntheticStudyError("contact credential was changed concurrently")
            changed = db.execute(
                "UPDATE pii.invitations SET token_hash=? "
                "WHERE learner_id=? AND token_hash=? AND state='registered'",
                (new_hash, ref, old_hash),
            )
            if changed.rowcount != 1:
                raise SyntheticStudyError("invitation credential was changed concurrently")
        return ref

    def _record(self, db, token: str, *, at: datetime):
        row=db.execute("SELECT * FROM pii.invitations WHERE token_hash=?",
                       (self.digest(token),)).fetchone()
        if row is None:
            raise SyntheticStudyError("invitation not found")
        if row["state"] != "registered" and row["expires_at"] < iso(at):
            raise SyntheticStudyError("invitation has expired")
        return row

    def status(self, token: str, *, at: datetime) -> dict:
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            state=row["state"]
            if state=="registered":
                self.store._authenticated(db,row["learner_id"],token)
                progress=self.store._state(db,row["learner_id"])
                return dict(stage="participant", phase=progress["phase"],
                            session=progress["session"],
                            index=progress["index"],
                            study_language=db.execute(
                                "SELECT study_language FROM participants "
                                "WHERE learner_id=?",(row["learner_id"],)
                            ).fetchone()[0])
            return dict(stage=state,language=row["consent_lang"] or "en")

    def consent_requirements(self, token: str, *, language: str,
                             at: datetime) -> dict:
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            statements, optional, version, eligible = required_for_recipient(
                language, row["email"]
            )
            return dict(required=list(statements), optional=optional,
                        version=version, ai_points_eligible=eligible,
                        no_email_exposed=True)

    def reward_eligible(self, token: str, *, at: datetime) -> bool:
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            return required_for_recipient("en",row["email"])[3]

    def consent(self, token: str, *, checks: list[bool], optional: bool,
                language: str, at: datetime) -> dict:
        if (type(checks) is not list or any(type(x) is not bool for x in checks)
                or not all(checks) or type(optional) is not bool
                or language not in ("en","fr")):
            raise SyntheticStudyError("all required declarations and optional choice")
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            if row["state"] != "invited":
                raise SyntheticStudyError("consent is not the next stage")
            statements, _, version, _ = required_for_recipient(
                language,row["email"]
            )
            if len(checks)!=len(statements):
                raise SyntheticStudyError("required declaration count mismatch")
            db.execute(
                "UPDATE pii.invitations SET state='consented',consent_lang=?,"
                "consent_at=?,optional=? WHERE token_hash=?",
                (language,iso(at),int(optional),self.digest(token)),
            )
        return dict(stage="screening",consent_version=version)

    def screening(self, token: str, *, answers: dict[str,str],
                  at: datetime) -> dict:
        if type(answers) is not dict:
            raise SyntheticStudyError("screening responses required")
        eligible,score=self.store.bank.eligible(
            econ_course=False,screening_answers=answers,
        )
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            if row["state"]!="consented":
                raise SyntheticStudyError("consent required before screening")
            if not eligible:
                # Approved exclusion record contains only time and score.
                db.execute(
                    "INSERT INTO screening_log(timestamp,score,eligible) "
                    "VALUES(?,?,0)",(iso(at),score),
                )
                db.execute("DELETE FROM pii.invitations WHERE token_hash=?",
                           (self.digest(token),))
                return dict(eligible=False,stage="excluded")
            db.execute(
                "UPDATE pii.invitations SET state='screened',answers_json=? "
                "WHERE token_hash=?",
                (dump(answers),self.digest(token)),
            )
            return dict(eligible=True,stage="registration")

    def exclude_prior_course(self, token: str, *, at: datetime) -> None:
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            if row["state"] not in ("invited","consented"):
                raise SyntheticStudyError("economics course exclusion is not due")
            db.execute("DELETE FROM pii.invitations WHERE token_hash=?",
                       (self.digest(token),))

    def register(self, token: str, *, age: int, program: str,
                 at: datetime) -> dict:
        if type(age) is not int or not 18<=age<=99:
            raise SyntheticStudyError("age must be 18..99")
        if program not in self.programs:
            raise SyntheticStudyError("choose an approved academic program")
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            if row["state"]!="screened" or not row["answers_json"]:
                raise SyntheticStudyError("eligibility screening not complete")
            # Read values from trusted private state, not from client fields.
            saved=dict(email=row["email"],language=row["consent_lang"],
                       optional=bool(row["optional"]),
                       consent_at=datetime.fromisoformat(row["consent_at"]),
                       answers=__import__("json").loads(row["answers_json"]))
        version=required_for_recipient(saved["language"],saved["email"])[2]
        result=self.store.register(
            contact_email=saved["email"],econ_course=False,
            screening_answers=saved["answers"],
            consent_version=version,consent_given=True,
            age=age,program=program,at=at,
            consent_lang=saved["language"],
            open_data_consent=saved["optional"],
            consent_at=saved["consent_at"],
            invitation_token=token,
        )
        if not result["eligible"]:
            raise SyntheticStudyError("inconsistent eligible screening")
        return dict(registered=True,stage="participant",session=1,phase="PRETEST")

    def learner(self, token: str, *, at: datetime):
        with self.store._tx() as db:
            row=self._record(db,token,at=at)
            if row["state"]!="registered":
                raise SyntheticStudyError("participant has not registered")
            self.store._authenticated(db,row["learner_id"],token)
            return row["learner_id"]
