"""Private administrative recruitment ledger for the three-arm study.

Separate from the pseudonymous research SQLite and the existing contacts vault.
This module provides tested, OFFLINE primitives; importing it never enables
real enrollment, sends email, changes live mode or creates public routes.
The supervisor distributes questionnaire links *personally*, outside this app.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3

ADMIN_EMAILS = {
    "wiam.belouard@aivancity.education": "researcher",
    "sara.elkardi@aivancity.education": "researcher",
    "davis.joseph@aivancity.education": "researcher",
    "yaacoub@aivancity.ai": "supervisor",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}\Z")
PASSWORD_ITERATIONS = 480000
SESSION_AGE = timedelta(hours=1)
SCHOOL_SUFFIX = "@aivancity.education"


class RecruitmentError(ValueError):
    pass


def utc(at: datetime) -> str:
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise RecruitmentError("timezone-aware time required")
    return at.astimezone(timezone.utc).isoformat()


def canonical_email(email: str) -> str:
    if type(email) is not str or len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise RecruitmentError("valid email address required")
    return email.casefold()


def _name(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if type(value) is not str or len(value) > 100 or any(
        ord(ch) < 32 or ch in "<>\\\"\x00" for ch in value
    ):
        raise RecruitmentError("invalid optional personal name")
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None


def _password_digest(password: str, *, salt: bytes | None = None) -> str:
    if type(password) is not str or not 18 <= len(password) <= 512:
        raise RecruitmentError("password must contain 18–512 characters")
    salt = secrets.token_bytes(16) if salt is None else salt
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${pbkdf2_hmac('sha256',password.encode(),salt,PASSWORD_ITERATIONS).hex()}"


def _password_valid(password: str, stored: str) -> bool:
    fields = stored.split("$")
    if len(fields) != 4 or fields[0] != "pbkdf2_sha256":
        return False
    try:
        rounds = int(fields[1])
        if not 300000 <= rounds <= 1000000:
            return False
        salt = bytes.fromhex(fields[2])
        expected = bytes.fromhex(fields[3])
        if len(salt) != 16 or len(expected) != 32:
            return False
        digest = pbkdf2_hmac("sha256",password.encode(),salt,rounds)
        return hmac.compare_digest(digest,expected)
    except (ValueError,TypeError,UnicodeEncodeError):
        return False


class RecruitmentLedger:
    """Restricted PII ledger. Never pass a row to an unauthenticated route."""

    def __init__(self, directory: Path):
        directory = Path(directory)
        if not directory.is_absolute() or directory.is_symlink():
            raise RecruitmentError("private absolute non-symlink directory required")
        if not directory.is_dir():
            raise RecruitmentError("provision protected directory before starting")
        if directory.stat().st_mode & 0o077:
            raise RecruitmentError("private directory must have mode 0700")
        self.file = directory / "supervisor_recruitment.sqlite3"
        if self.file.is_symlink():
            raise RecruitmentError("symlinked recruitment file refused")
        with self._tx() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS candidates(
                  candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                  first_name TEXT,
                  last_name TEXT,
                  questionnaire TEXT NOT NULL CHECK(questionnaire IN ('school','external')),
                  language TEXT NOT NULL CHECK(language IN ('en','fr')),
                  consent_timestamp TEXT NOT NULL,
                  submitted_at TEXT NOT NULL,
                  approved_for_invitation INTEGER NOT NULL DEFAULT 0,
                  invited_at TEXT,
                  invitation_status TEXT NOT NULL DEFAULT 'potential'
                    CHECK(invitation_status IN ('potential','prepared','accepted')),
                  UNIQUE(email)
                );
                CREATE TABLE IF NOT EXISTS administrators(
                  email TEXT PRIMARY KEY,
                  role TEXT NOT NULL CHECK(role IN ('researcher','supervisor')),
                  password_hash TEXT NOT NULL,
                  must_change_password INTEGER NOT NULL DEFAULT 1,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  failures INTEGER NOT NULL DEFAULT 0,
                  locked_until TEXT
                );
                CREATE TABLE IF NOT EXISTS admin_sessions(
                  session_hash TEXT PRIMARY KEY,
                  admin_email TEXT NOT NULL REFERENCES administrators(email),
                  csrf_hash TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit(
                  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  at TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  subject_id INTEGER,
                  details TEXT
                );
                CREATE TABLE IF NOT EXISTS policy(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  changed_at TEXT NOT NULL,
                  changed_by TEXT NOT NULL
                );
                INSERT OR IGNORE INTO policy VALUES(
                  'automatic_reminders_enabled','0','1970-01-01T00:00:00+00:00','initial');
            """)
        os.chmod(self.file,0o600)

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.file,timeout=12,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=12000")
        db.execute("PRAGMA secure_delete=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def apply(self, *, email: str, first_name: str | None = None,
              last_name: str | None = None, questionnaire: str,
              language: str, privacy_accepted: bool, at: datetime) -> dict:
        """Store interest, not enrollment or consent to the actual RCT.

        A duplicate request returns the same generic result without changing
        the prior record or allowing email-based identity enumeration.
        """
        address = canonical_email(email)
        if questionnaire not in ("school","external") or language not in ("en","fr"):
            raise RecruitmentError("invalid questionnaire or language")
        if questionnaire=="school" and not address.endswith(SCHOOL_SUFFIX):
            raise RecruitmentError("school questionnaire requires institutional email")
        if questionnaire=="external" and address.endswith(SCHOOL_SUFFIX):
            raise RecruitmentError("institutional email must use school questionnaire")
        if privacy_accepted is not True:
            raise RecruitmentError("recruitment privacy information must be accepted")
        first,last = _name(first_name),_name(last_name)
        t=utc(at)
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO candidates"
                "(email,first_name,last_name,questionnaire,language,"
                "consent_timestamp,submitted_at) VALUES(?,?,?,?,?,?,?)",
                (address,first,last,questionnaire,language,t,t),
            )
        return dict(received=True,participant_enrolled=False)

    def provision(self, *, email: str, temporary_password: str,
                  at: datetime) -> None:
        address=canonical_email(email)
        if address not in ADMIN_EMAILS:
            raise RecruitmentError("email is not in approved administrator allowlist")
        digest=_password_digest(temporary_password)
        with self._tx() as db:
            if db.execute("SELECT 1 FROM administrators WHERE email=?",(address,)).fetchone():
                raise RecruitmentError("existing user: explicit password rotation required")
            db.execute(
                "INSERT INTO administrators(email,role,password_hash) VALUES(?,?,?)",
                (address,ADMIN_EMAILS[address],digest),
            )
            db.execute("INSERT INTO audit(at,actor,action) VALUES(?,?,?)",
                       (utc(at),address,"provisioned"))

    def login(self, *, email: str, password: str, at: datetime):
        address=canonical_email(email)
        t=utc(at)
        denied=False
        result=None
        with self._tx() as db:
            row=db.execute("SELECT * FROM administrators WHERE email=?",
                           (address,)).fetchone()
            # A single error for bad user/password (no account enumeration).
            if row is None or row["enabled"]!=1:
                denied=True
            elif row["locked_until"] and row["locked_until"]>t:
                denied=True
            elif not _password_valid(password,row["password_hash"]):
                fails=row["failures"]+1
                locked=utc(at+timedelta(minutes=15)) if fails>=5 else None
                db.execute("UPDATE administrators SET failures=?,locked_until=? WHERE email=?",
                           (fails,locked,address))
                denied=True
            else:
                db.execute("UPDATE administrators SET failures=0,locked_until=NULL WHERE email=?",
                           (address,))
                session=secrets.token_urlsafe(48)
                csrf=secrets.token_urlsafe(32)
                db.execute("INSERT INTO admin_sessions VALUES(?,?,?,?,?)",
                           (sha256(session.encode()).hexdigest(),address,
                            sha256(csrf.encode()).hexdigest(),utc(at+SESSION_AGE),t))
                result=dict(cookie=session,csrf=csrf,role=row["role"],
                            must_change_password=bool(row["must_change_password"]))
        # Reject *after* transaction commits so lockout counters persist.
        if denied:
            raise RecruitmentError("invalid credentials")
        return result

    def authenticate(self, *, cookie: str, at: datetime,
                     csrf: str | None = None, mutation: bool = False) -> dict:
        if type(cookie) is not str or not 35 <= len(cookie) <= 200:
            raise RecruitmentError("admin login required")
        digest=sha256(cookie.encode()).hexdigest()
        with self._tx() as db:
            row=db.execute(
                "SELECT a.email,a.role,a.enabled,a.must_change_password,"
                "s.csrf_hash,s.expires_at FROM admin_sessions s "
                "JOIN administrators a ON a.email=s.admin_email "
                "WHERE s.session_hash=?",(digest,),
            ).fetchone()
        if row is None or not row["enabled"] or row["expires_at"]<=utc(at):
            raise RecruitmentError("admin login required")
        if mutation:
            if type(csrf) is not str or not hmac.compare_digest(
                sha256(csrf.encode()).hexdigest(),row["csrf_hash"]
            ):
                raise RecruitmentError("invalid CSRF token")
            if row["must_change_password"]:
                raise RecruitmentError("change your temporary password first")
        return dict(email=row["email"],role=row["role"],
                    must_change_password=bool(row["must_change_password"]))

    def rotate_password(self, *, cookie: str, csrf: str,
                        current: str, replacement: str, at: datetime) -> None:
        user=self.authenticate(cookie=cookie,at=at,csrf=csrf,mutation=False)
        # Verify CSRF even for the initial password-change endpoint.
        digest=sha256(cookie.encode()).hexdigest()
        with self._tx() as db:
            session=db.execute("SELECT csrf_hash FROM admin_sessions WHERE session_hash=?",
                               (digest,)).fetchone()
            if session is None or not hmac.compare_digest(
                session["csrf_hash"],sha256(csrf.encode()).hexdigest()
            ):
                raise RecruitmentError("invalid CSRF token")
            old=db.execute("SELECT password_hash FROM administrators WHERE email=?",
                           (user["email"],)).fetchone()["password_hash"]
            if not _password_valid(current,old) or _password_valid(replacement,old):
                raise RecruitmentError("current password invalid or replacement unchanged")
            new=_password_digest(replacement)
            db.execute("UPDATE administrators SET password_hash=?,"
                       "must_change_password=0,failures=0,locked_until=NULL WHERE email=?",
                       (new,user["email"]))
            db.execute("DELETE FROM admin_sessions WHERE admin_email=? AND session_hash<>?",
                       (user["email"],digest))
            db.execute("INSERT INTO audit(at,actor,action) VALUES(?,?,?)",
                       (utc(at),user["email"],"password_changed"))

    def candidates(self) -> list[dict]:
        with self._tx() as db:
            return [dict(row) for row in db.execute(
                "SELECT candidate_id,email,first_name,last_name,questionnaire,"
                "language,submitted_at,approved_for_invitation,invitation_status "
                "FROM candidates ORDER BY candidate_id DESC"
            )]

    def approve(self, *, ids: list[int], actor: str, at: datetime) -> int:
        """Admin approves selected intake records; no emails are sent here."""
        if type(ids) is not list or not 1 <= len(ids) <= 1000 or any(
            type(v) is not int or v<1 for v in ids
        ) or len(set(ids))!=len(ids):
            raise RecruitmentError("1–1000 distinct candidate IDs required")
        with self._tx() as db:
            placeholders=",".join("?" for _ in ids)
            changed=db.execute(
                "UPDATE candidates SET approved_for_invitation=1 "
                f"WHERE candidate_id IN ({placeholders}) "
                "AND invitation_status='potential'",ids,
            ).rowcount
            db.execute("INSERT INTO audit(at,actor,action,details) VALUES(?,?,?,?)",
                       (utc(at),actor,"candidate_approval",str(changed)))
        return changed

    def reminder_enabled(self) -> bool:
        with self._tx() as db:
            return db.execute("SELECT value FROM policy WHERE key=?",
                              ("automatic_reminders_enabled",)).fetchone()[0]=="1"

    def set_reminder_enabled(self, *, enabled: bool, actor: str, at: datetime) -> None:
        if type(enabled) is not bool or actor not in ADMIN_EMAILS:
            raise RecruitmentError("approved administrator and boolean required")
        with self._tx() as db:
            db.execute("UPDATE policy SET value=?,changed_at=?,changed_by=? "
                       "WHERE key='automatic_reminders_enabled'",
                       ("1" if enabled else "0",utc(at),actor))
            db.execute("INSERT INTO audit(at,actor,action) VALUES(?,?,?)",
                       (utc(at),actor,"reminder_enabled" if enabled else "reminder_disabled"))
