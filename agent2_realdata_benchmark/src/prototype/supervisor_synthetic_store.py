"""Private, SQLite-backed synthetic supervisor parallel-group session runtime.

This is an isolated integration harness, NOT a released student application.
It accepts only .test contacts and automatically generated SYN_SUPERVISOR_ IDs.
No human enrollment route, email service, or real participant credentials.
The eight research tables and separate contact database are an implementation
of data_to_save.docx, with append-only event/state history.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3

from .supervisor_content import SupervisorBank
from .supervisor_trace_engine import SupervisorTraceEngine, SESSION_BLOCKS

GROUPS = ("A", "B", "C")
FORMS = ("PRETEST", "QUIZ", "POSTTEST", "SURVEY",
         "WAITING_NEXT_SESSION", "DONE")


def iso(at: datetime) -> str:
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return at.astimezone(timezone.utc).isoformat()


def dump(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class SyntheticStudyError(ValueError):
    pass


class SupervisorSyntheticStore:
    """Bank-pinned, synthetic-only participant state and append-only audit log."""

    def __init__(self, folder: str | Path, *, bank: SupervisorBank):
        self.folder = Path(folder)
        if not self.folder.is_dir() or self.folder.is_symlink():
            raise SyntheticStudyError("existing nonsymlink private directory required")
        if not isinstance(bank, SupervisorBank):
            raise TypeError("supervisor bank is required")
        self.bank = bank
        self.research = self.folder / "supervisor_fictional_study.sqlite3"
        self.contacts = self.folder / "supervisor_fictional_contacts.sqlite3"
        if self.research.is_symlink() or self.contacts.is_symlink():
            raise SyntheticStudyError("symlinked databases refused")
        with self._tx() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS config (
                config_version TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                app_commit TEXT NOT NULL,
                files_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS participants (
                learner_id TEXT PRIMARY KEY,
                grp TEXT NOT NULL CHECK(grp IN ('A','B','C')),
                registered_at TEXT NOT NULL,
                consent_version TEXT NOT NULL,
                consent_at TEXT NOT NULL,
                consent_lang TEXT NOT NULL DEFAULT 'en',
                open_data_consent INTEGER NOT NULL DEFAULT 0,
                econ_course INTEGER NOT NULL,
                screening_score INTEGER NOT NULL,
                eligible INTEGER NOT NULL CHECK(eligible=1),
                age INTEGER,
                program TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                missed_sessions INTEGER NOT NULL DEFAULT 0,
                status_changed_at TEXT NOT NULL,
                config_version TEXT NOT NULL REFERENCES config(config_version)
              );
              CREATE TABLE IF NOT EXISTS screening_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 6 AND 8),
                eligible INTEGER NOT NULL CHECK(eligible=0)
              );
              CREATE TABLE IF NOT EXISTS deletion_log (
                learner_id TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                channel TEXT NOT NULL CHECK(channel IN ('website','email'))
              );
              CREATE TABLE IF NOT EXISTS erasure_authorization (
                one INTEGER PRIMARY KEY CHECK(one=1)
              );
              CREATE TABLE IF NOT EXISTS sessions (
                learner_id TEXT NOT NULL REFERENCES participants(learner_id),
                session_no INTEGER NOT NULL CHECK(session_no IN (1,2,3)),
                scheduled_for TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'scheduled',
                PRIMARY KEY(learner_id,session_no)
              );
              CREATE TABLE IF NOT EXISTS learner_state (
                learner_id TEXT PRIMARY KEY REFERENCES participants(learner_id),
                updated_at TEXT NOT NULL,
                session_no INTEGER NOT NULL,
                step TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                pending_recovery TEXT,
                state_json TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL REFERENCES participants(learner_id),
                session_no INTEGER NOT NULL,
                request_id TEXT NOT NULL UNIQUE,
                shown_at TEXT NOT NULL,
                answered_at TEXT NOT NULL,
                response_time_ms INTEGER NOT NULL,
                phase TEXT NOT NULL,
                block_index INTEGER,
                mode TEXT,
                action_type TEXT NOT NULL,
                question_id TEXT,
                concept_id TEXT,
                bloom_level INTEGER,
                options_shown TEXT,
                answer_given TEXT,
                is_correct INTEGER,
                content_id TEXT,
                free_text TEXT,
                mastery_before REAL,
                mastery_after REAL,
                D_before REAL,
                D_after REAL,
                bloom_after INTEGER,
                rule_tags TEXT,
                trigger TEXT,
                recovery_attempt TEXT,
                recovery_outcome TEXT
              );
              CREATE TABLE IF NOT EXISTS state_history (
                event_id INTEGER PRIMARY KEY REFERENCES events(event_id),
                learner_id TEXT NOT NULL REFERENCES participants(learner_id),
                state_json TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS surveys (
                learner_id TEXT NOT NULL REFERENCES participants(learner_id),
                session_no INTEGER NOT NULL,
                submitted_at TEXT NOT NULL,
                Q1 INTEGER NOT NULL CHECK(Q1 BETWEEN 1 AND 7),
                Q2 INTEGER NOT NULL CHECK(Q2 BETWEEN 1 AND 7),
                Q3 INTEGER NOT NULL CHECK(Q3 BETWEEN 1 AND 7),
                Q4 INTEGER NOT NULL CHECK(Q4 BETWEEN 1 AND 7),
                Q5 INTEGER NOT NULL CHECK(Q5 BETWEEN 1 AND 7),
                Q6 INTEGER NOT NULL CHECK(Q6 BETWEEN 1 AND 7),
                time_ms INTEGER NOT NULL,
                PRIMARY KEY(learner_id,session_no)
              );
              CREATE TRIGGER IF NOT EXISTS no_event_update
                BEFORE UPDATE ON events BEGIN
                  SELECT RAISE(ABORT,'events append-only');
                END;
              DROP TRIGGER IF EXISTS no_event_delete;
              CREATE TRIGGER no_event_delete
                BEFORE DELETE ON events
                WHEN NOT EXISTS(SELECT one FROM erasure_authorization)
                BEGIN SELECT RAISE(ABORT,'events append-only'); END;
              CREATE TRIGGER IF NOT EXISTS no_history_update
                BEFORE UPDATE ON state_history BEGIN
                  SELECT RAISE(ABORT,'history append-only');
                END;
              DROP TRIGGER IF EXISTS no_history_delete;
              CREATE TRIGGER no_history_delete
                BEFORE DELETE ON state_history
                WHEN NOT EXISTS(SELECT one FROM erasure_authorization)
                BEGIN SELECT RAISE(ABORT,'history append-only'); END;
            """)
            db.executescript("""
              CREATE TABLE IF NOT EXISTS pii.contacts (
                learner_id TEXT PRIMARY KEY,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                token_hash TEXT NOT NULL UNIQUE,
                token_created_at TEXT NOT NULL,
                reminders_sent TEXT NOT NULL DEFAULT '[]'
              );
            """)
            participant_fields = {row["name"] for row in db.execute(
                "PRAGMA table_info(participants)"
            )}
            if "consent_lang" not in participant_fields:
                db.execute("ALTER TABLE participants ADD COLUMN consent_lang "
                           "TEXT NOT NULL DEFAULT 'en'")
            if "open_data_consent" not in participant_fields:
                db.execute("ALTER TABLE participants ADD COLUMN open_data_consent "
                           "INTEGER NOT NULL DEFAULT 0")
            row = db.execute(
                "SELECT files_json FROM config WHERE config_version=?",
                ("supervisor_20261111_v1",),
            ).fetchone()
            hashes = dump(self.bank.sha256)
            if row and row["files_json"] != hashes:
                raise SyntheticStudyError("bank changes cannot mutate a live configuration")
            if not row:
                db.execute(
                    "INSERT INTO config VALUES(?,?,?,?,?)", (
                        "supervisor_20261111_v1",
                        datetime.now(timezone.utc).isoformat(),
                        "SUPERVISOR_PARALLEL_OFFLINE_ONLY",
                        hashes,
                        dump({
                            "p_learn": .10, "p_slip": .10, "p_guess": .25,
                            "initial": [0.20,0.50,0.75],
                            "blocks": list(SESSION_BLOCKS),
                            "max_recoveries_per_session": 2,
                            "max_recoveries_per_concept": 2,
                            "drop_from_peak": .25,
                            "recovered_threshold": .50,
                            "screening_exclusion": 6,
                            "fatigue_items": 6,
                        }),
                    ),
                )
        for path in (self.research, self.contacts):
            path.chmod(0o600)

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.research, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("ATTACH DATABASE ? AS pii", (str(self.contacts),))
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _ref(ref: str):
        if (not isinstance(ref, str) or
                not re.fullmatch(r"SYN_SUPERVISOR_P\d{3,8}", ref)):
            raise SyntheticStudyError("fictional learner reference required")

    def _authenticated(self, db, ref: str, token: str):
        self._ref(ref)
        if not isinstance(token, str) or len(token) < 32:
            raise SyntheticStudyError("invalid fictional token")
        row = db.execute(
            "SELECT token_hash FROM pii.contacts WHERE learner_id=?", (ref,)
        ).fetchone()
        if (row is None or not secrets.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), row["token_hash"]
        )):
            raise SyntheticStudyError("invalid fictional token")
        status = db.execute(
            "SELECT status FROM participants WHERE learner_id=?", (ref,)
        ).fetchone()
        if status is None or status["status"] in ("withdrawn", "removed"):
            raise SyntheticStudyError("fictional participant is inactive")

    def _state(self, db, ref):
        row = db.execute(
            "SELECT state_json FROM learner_state WHERE learner_id=?", (ref,)
        ).fetchone()
        if row is None:
            raise SyntheticStudyError("unknown fictional participant")
        return json.loads(row["state_json"])

    @staticmethod
    def _response_ms(shown_at: datetime, answered_at: datetime) -> int:
        start, stop = datetime.fromisoformat(iso(shown_at)), datetime.fromisoformat(iso(answered_at))
        delta = (stop - start).total_seconds() * 1000
        if not 0 <= delta <= 86_400_000:
            raise SyntheticStudyError("response time outside accepted range")
        return round(delta)

    def _append(self, db, ref, state, *, request_id: str,
                shown_at: datetime, answered_at: datetime,
                phase: str, action: str, question_id=None,
                concept=None, level=None, block_index=None,
                mode=None, options_shown="", choice=None,
                correct=None, before=None, after=None,
                D_before=None, D_after=None, rule_tags="",
                trigger="", recovery_attempt="", recovery_outcome="",
                content_id=None, free_text=None):
        if (not isinstance(request_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request_id)):
            raise SyntheticStudyError("unique request ID required")
        ms = self._response_ms(shown_at, answered_at)
        current = db.execute(
            "SELECT event_id FROM events WHERE request_id=?", (request_id,)
        ).fetchone()
        if current:
            raise SyntheticStudyError("duplicate request ID rejected")
        db.execute(
            """UPDATE learner_state SET updated_at=?,session_no=?,step=?,
               step_index=?,pending_recovery=?,state_json=? WHERE learner_id=?""",
            (iso(answered_at), state["session"], state["phase"],
             state["index"], state.get("pending_recovery"),
             dump(state), ref),
        )
        cur = db.execute(
            """INSERT INTO events(
                learner_id,session_no,request_id,shown_at,answered_at,
                response_time_ms,phase,block_index,mode,action_type,
                question_id,concept_id,bloom_level,options_shown,answer_given,
                is_correct,content_id,free_text,mastery_before,mastery_after,
                D_before,D_after,bloom_after,rule_tags,trigger,
                recovery_attempt,recovery_outcome
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ref, state["session"], request_id, iso(shown_at),
             iso(answered_at), ms, phase, block_index, mode, action,
             question_id, concept, level, options_shown, choice,
             None if correct is None else int(correct),
             content_id, free_text, before, after, D_before, D_after,
             state["engine"]["bloom"][concept] if concept and state.get("engine") else None,
             rule_tags, trigger, recovery_attempt, recovery_outcome),
        )
        db.execute(
            "INSERT INTO state_history(event_id,learner_id,state_json) VALUES(?,?,?)",
            (cur.lastrowid, ref, dump(state)),
        )
        return cur.lastrowid

    def register(self, *, contact_email: str,
                 econ_course: bool, screening_answers: dict[str, str],
                 consent_version: str, consent_given: bool,
                 age: int | None, program: str, at: datetime,
                 consent_lang: str = "en",
                 open_data_consent: bool = False,
                 consent_at: datetime | None = None) -> dict:
        """Eligible fictional candidates alone consume the A/B/C rotation."""
        if (consent_given is not True or not isinstance(consent_version, str)
                or not consent_version.strip()):
            raise SyntheticStudyError("explicit versioned consent required")
        eligible, score = self.bank.eligible(
            econ_course=econ_course,
            screening_answers=screening_answers,
        )
        if not eligible:
            return {"eligible": False, "screening_score": score,
                    "group_assigned": False, "synthetic_only": True}
        if (not isinstance(contact_email, str)
                or not re.fullmatch(
                    r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.test",
                    contact_email, flags=re.IGNORECASE)):
            raise SyntheticStudyError("only invented .test email accounts permitted")
        if age is not None and (
                type(age) is not int or not 18 <= age <= 120):
            raise SyntheticStudyError("invalid fictional age")
        if not isinstance(program, str) or len(program) > 160:
            raise SyntheticStudyError("invalid fictional academic program")
        if consent_lang not in ("en", "fr") or type(open_data_consent) is not bool:
            raise SyntheticStudyError("explicit consent language and optional choice required")
        if age is None or age > 99:
            raise SyntheticStudyError("fictional age must be between 18 and 99")
        if not isinstance(program, str) or not program.strip():
            raise SyntheticStudyError("academic program required")
        consent_clicked = iso(consent_at if consent_at is not None else at)
        now = iso(at)
        token = secrets.token_urlsafe(40)
        with self._tx() as db:
            if db.execute(
                "SELECT 1 FROM pii.contacts WHERE email=? COLLATE NOCASE",
                (contact_email,),
            ).fetchone():
                raise SyntheticStudyError(
                    "This email is already registered. Use the link sent to you by email."
                )
            ordinal = (db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
                       + db.execute("SELECT COUNT(*) FROM deletion_log").fetchone()[0])
            ref = f"SYN_SUPERVISOR_P{ordinal + 1:03d}"
            group = GROUPS[ordinal % 3]
            db.execute(
                """INSERT INTO participants(
                   learner_id,grp,registered_at,consent_version,consent_at,
                   consent_lang,open_data_consent,
                   econ_course,screening_score,eligible,age,program,status,
                   missed_sessions,status_changed_at,config_version
                 ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ref, group, now, consent_version, consent_clicked, consent_lang,
                 int(open_data_consent), int(econ_course), score, 1, age,
                 program, "active", 0, now, "supervisor_20261111_v1"),
            )
            db.execute(
                "INSERT INTO pii.contacts(learner_id,email,token_hash,token_created_at)"
                " VALUES(?,?,?,?)",
                (ref, contact_email,
                 hashlib.sha256(token.encode()).hexdigest(), now),
            )
            for i, offset in enumerate((0, 4, 8), 1):
                db.execute(
                    "INSERT INTO sessions(learner_id,session_no,scheduled_for,"
                    "started_at,status) VALUES(?,?,?,?,?)",
                    (ref, i, iso(at + timedelta(days=offset)),
                     now if i == 1 else None,
                     "in_progress" if i == 1 else "scheduled"),
                )
            state = dict(phase="PRETEST", session=1, index=0,
                         pretest_answers={}, posttest_answers={},
                         engine=None, pending_recovery=None)
            db.execute(
                "INSERT INTO learner_state VALUES(?,?,?,?,?,?,?)",
                (ref,now,1,"PRETEST",0,None,dump(state)),
            )
            # Screen each scored screening item as an append-only event
            # without linking the actual email or revealing treatment.
            for i, item in enumerate(self.bank.forms["screening"]):
                self._append(
                    db, ref, state, request_id=f"{ref}_screen_{i:02d}",
                    shown_at=at, answered_at=at,
                    phase="SCREENING", action="QUESTION",
                    question_id=item.question_id,
                    concept=item.concept, level=item.level,
                    options_shown="ABCD",
                    choice=screening_answers[item.question_id],
                    correct=self.bank.grade(
                        item.question_id,
                        screening_answers[item.question_id],
                        form="screening",
                    ),
                )
        return {"eligible": True, "screening_score": score,
                "fictional_learner_id": ref,
                "fictional_private_token": token,
                "synthetic_only": True}

    def progress(self, ref: str, token: str) -> dict:
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
        return {
            "phase": state["phase"], "session": state["session"],
            "index": state["index"], "synthetic_only": True,
            "human_enrollment_authorized": False,
        }

    def next_item(self, ref: str, token: str):
        """No answer key, group, contact, token hash or private state is returned."""
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
        if state["phase"] in ("PRETEST", "POSTTEST"):
            form = state["phase"].lower()
            item = self.bank.forms[form][state["index"]]
            return dict(kind="question", phase=state["phase"],
                        **item.public(), synthetic_only=True)
        if state["phase"] == "QUIZ":
            engine = SupervisorTraceEngine.restore(state["engine"])
            step = engine.next_action()
            if step is None:
                return dict(kind="block_complete", synthetic_only=True)
            if step["qid"] != "—":
                item = self.bank.get(step["qid"], form="practice")
                options = item.public()["options"]
                if step["action"] == "DROP_2":
                    distractor = next(k for k in "ABCD"
                                      if k != item.correct_answer)
                    options = {k: options[k]
                               for k in "ABCD"
                               if k in (distractor, item.correct_answer)}
                return dict(kind="question" if step["action"] == "QUESTION"
                            else "recovery", action=step["action"],
                            question_id=item.question_id,
                            question_text=item.question_text,
                            options=options, synthetic_only=True)
            return dict(kind="recovery", action=step["action"],
                        content_status="REQUIRES_INDEPENDENT_REVIEW",
                        synthetic_only=True)
        return dict(kind=state["phase"].lower(), synthetic_only=True)

    def answer_assessment(self, ref: str, token: str, *,
                          request_id: str, item_id: str, choice: str,
                          shown_at: datetime, answered_at: datetime) -> dict:
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
            phase = state["phase"]
            if phase not in ("PRETEST", "POSTTEST"):
                raise SyntheticStudyError("independent assessment not active")
            form = phase.lower()
            item = self.bank.forms[form][state["index"]]
            if item.question_id != item_id:
                raise SyntheticStudyError("assessment item is not next in sequence")
            score = self.bank.grade(item_id, choice, form=form)
            state[form + "_answers"][item_id] = choice
            state["index"] += 1
            if state["index"] == 16:
                if phase == "PRETEST":
                    initial = self.bank.initialize_qmatrix(
                        state["pretest_answers"])
                    participant = db.execute(
                        "SELECT grp FROM participants WHERE learner_id=?", (ref,)
                    ).fetchone()
                    engine = SupervisorTraceEngine(participant["grp"], initial)
                    state["engine"] = engine.snapshot()
                    state["phase"] = "QUIZ"
                else:
                    state["phase"] = "SURVEY"
                state["index"] = 0
            self._append(
                db, ref, state, request_id=request_id,
                shown_at=shown_at, answered_at=answered_at,
                phase=phase, action="QUESTION", question_id=item_id,
                concept=item.concept, level=item.level,
                options_shown="ABCD", choice=choice, correct=score,
            )
        # Never return immediate correctness or assessment scores.
        return {"accepted": True, "synthetic_only": True}

    def answer_quiz(self, ref: str, token: str, *,
                    request_id: str, item_id: str | None, choice: str | None,
                    shown_at: datetime, answered_at: datetime) -> dict:
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
            if state["phase"] != "QUIZ":
                raise SyntheticStudyError("adaptive block not active")
            engine = SupervisorTraceEngine.restore(state["engine"])
            step = engine.next_action()
            if step is None or step["qid"] != (item_id or "—"):
                raise SyntheticStudyError("the pending step must be completed in order")
            concept = step["concept"]
            before, D_before = engine.mastery[concept], engine.degradation
            action = step["action"]
            if action in ("QUESTION", "DROP_2", "SOCRATIC_HINT"):
                if type(choice) is not str or choice not in "ABCD":
                    raise SyntheticStudyError("A/B/C/D answer required")
                correct = self.bank.grade(item_id, choice, form="practice")
                if action == "DROP_2":
                    item = self.bank.get(item_id, form="practice")
                    distractor = next(k for k in "ABCD"
                                      if k != item.correct_answer)
                    if choice not in (item.correct_answer, distractor):
                        raise SyntheticStudyError("DROP_2 accepts exactly two shown options")
                scripted = "correct" if correct else "wrong"
                options_shown = (
                    "".join(k for k in "ABCD"
                            if k in (self.bank.get(item_id, form="practice").correct_answer,
                                     next(t for t in "ABCD" if t != self.bank.get(item_id, form="practice").correct_answer)))
                    if action == "DROP_2" else "ABCD"
                )
            else:
                if choice is not None:
                    raise SyntheticStudyError("reading step takes no scored answer")
                correct = None
                scripted = ""
                options_shown = ""
            number = engine.question_in_session + (action == "QUESTION")
            completed_step = engine.submit(scripted)
            state["engine"] = engine.snapshot()
            state["index"] = engine.question_in_session
            state["pending_recovery"] = (
                engine.pending[0]["action"] if engine.pending else None)
            if engine.next_action() is None:
                state["phase"] = "POSTTEST" if state["session"] == 3 else "SURVEY"
                state["index"] = 0
            self._append(
                db, ref, state, request_id=request_id,
                shown_at=shown_at, answered_at=answered_at,
                phase="QUIZ", action=action,
                question_id=None if step["qid"] == "—" else item_id,
                concept=concept, level=step["level"],
                mode=step["mode"],
                block_index=number if action == "QUESTION" else None,
                options_shown=options_shown,
                choice=choice, correct=correct, before=before,
                after=engine.mastery[concept], D_before=D_before,
                D_after=engine.degradation,
                rule_tags=completed_step.get("rule_tags", ""),
                trigger=completed_step.get("trigger", ""),
                recovery_attempt=completed_step.get("recovery_attempt", ""),
                recovery_outcome=completed_step.get("recovery_outcome", ""),
                content_id=(
                    "UNREVIEWED_RESOURCE_" + action
                    if action in ("CONCEPT_SUMMARY", "WORKED_EXAMPLE")
                    else None
                ),
            )
        return {"accepted": True, "synthetic_only": True}

    def submit_survey(self, ref: str, token: str, *,
                      values: tuple[int, int, int, int, int, int],
                      time_ms: int, request_id: str, at: datetime) -> dict:
        if (len(values) != 6 or any(
                type(v) is not int or not 1 <= v <= 7 for v in values)
                or type(time_ms) is not int or time_ms < 0):
            raise SyntheticStudyError("six validated 1..7 fatigue responses required")
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
            if state["phase"] != "SURVEY":
                raise SyntheticStudyError("fatigue survey is not due")
            session = state["session"]
            db.execute(
                "INSERT INTO surveys VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ref, session, iso(at), *values, time_ms),
            )
            db.execute(
                "UPDATE sessions SET ended_at=?,status='completed' "
                "WHERE learner_id=? AND session_no=?",
                (iso(at), ref, session),
            )
            if session == 3:
                state["phase"] = "DONE"
                db.execute(
                    "UPDATE participants SET status='completed',"
                    "status_changed_at=? WHERE learner_id=?",
                    (iso(at), ref),
                )
            else:
                state["phase"] = "WAITING_NEXT_SESSION"
                state["index"] = 0
            self._append(
                db, ref, state, request_id=request_id,
                shown_at=at - timedelta(milliseconds=time_ms),
                answered_at=at, phase="SURVEY",
                action="SURVEY", content_id="SIX_ITEM_NASA_TLX_UNREVIEWED",
            )
        return {"accepted": True, "session_completed": session,
                "synthetic_only": True}

    def open_next_session(self, ref: str, token: str, at: datetime):
        with self._tx() as db:
            self._authenticated(db, ref, token)
            state = self._state(db, ref)
            if state["phase"] != "WAITING_NEXT_SESSION":
                raise SyntheticStudyError("next session is not scheduled")
            next_n = state["session"] + 1
            next_session = db.execute(
                "SELECT scheduled_for,status FROM sessions "
                "WHERE learner_id=? AND session_no=?",
                (ref, next_n),
            ).fetchone()
            if not next_session or next_session["status"] != "scheduled":
                raise SyntheticStudyError("next visit not scheduled")
            if iso(at) < next_session["scheduled_for"]:
                raise SyntheticStudyError("next session date has not arrived")
            engine = SupervisorTraceEngine.restore(state["engine"])
            engine.new_session(next_n)
            state.update(
                phase="QUIZ", session=next_n, index=0,
                engine=engine.snapshot(), pending_recovery=None,
            )
            db.execute(
                "UPDATE learner_state SET session_no=?,step='QUIZ',step_index=0,"
                "pending_recovery=NULL,updated_at=?,state_json=? WHERE learner_id=?",
                (next_n,iso(at),dump(state),ref),
            )
            db.execute(
                "UPDATE sessions SET status='in_progress',started_at=? "
                "WHERE learner_id=? AND session_no=?",
                (iso(at),ref,next_n),
            )
        return {"session_started": next_n, "synthetic_only": True}

    def mark_missed(self, ref: str, token: str, *,
                    at: datetime, reschedule_for: datetime | None):
        """Two missed visits remove the learner. A retry must be <=48h away."""
        with self._tx() as db:
            self._authenticated(db,ref,token)
            state = self._state(db,ref)
            if state["phase"] != "WAITING_NEXT_SESSION":
                raise SyntheticStudyError("only upcoming sessions may be missed")
            n = state["session"] + 1
            row = db.execute(
                "SELECT missed_sessions FROM participants WHERE learner_id=?",
                (ref,),
            ).fetchone()
            misses = row["missed_sessions"] + 1
            db.execute(
                "UPDATE participants SET missed_sessions=?,status=?,"
                "status_changed_at=? WHERE learner_id=?",
                (misses,"removed" if misses >= 2 else "active",iso(at),ref),
            )
            if misses < 2:
                if (reschedule_for is None or
                        not timedelta(0) <= (
                            datetime.fromisoformat(iso(reschedule_for)) -
                            datetime.fromisoformat(iso(at))) <= timedelta(days=2)):
                    raise SyntheticStudyError("reschedule must occur within two days")
                db.execute(
                    "UPDATE sessions SET scheduled_for=?,status='scheduled' "
                    "WHERE learner_id=? AND session_no=?",
                    (iso(reschedule_for),ref,n),
                )
            else:
                db.execute(
                    "UPDATE sessions SET status='missed' "
                    "WHERE learner_id=? AND session_no=?",
                    (ref,n),
                )
                db.execute(
                    "UPDATE pii.contacts SET token_hash=? WHERE learner_id=?",
                    (hashlib.sha256(secrets.token_bytes(48)).hexdigest(), ref),
                )
        return {"missed_count": misses,
                "removed": misses >= 2, "synthetic_only": True}

    def export_anonymous_events(self, *, ref: str, token: str) -> list[dict]:
        """Caller-authenticated synthetic data; never join personal contacts."""
        with self._tx() as db:
            self._authenticated(db,ref,token)
            return [
                dict(row) for row in db.execute(
                    "SELECT * FROM events WHERE learner_id=? ORDER BY event_id",
                    (ref,),
                )
            ]


    def log_screening_exclusion(self, score: int, *, at: datetime) -> None:
        """Anonymously record only an excluded 6..8 score and its time."""
        if type(score) is not int or not 6 <= score <= 8:
            raise SyntheticStudyError("only excluded screening results can be logged")
        with self._tx() as db:
            db.execute(
                "INSERT INTO screening_log(timestamp,score,eligible) VALUES(?,?,0)",
                (iso(at),score),
            )

    def withdraw(self, ref: str, token: str, *,
                 delete: bool, at: datetime, channel: str = "website") -> dict:
        """Atomic fictional erasure or stop/keep; no external mail delivery.

        The confirmation address is for the isolated trusted preview worker
        only. No real send is performed, and a real verified sender is a
        separate deployment gate.
        """
        if type(delete) is not bool or channel not in ("website","email"):
            raise SyntheticStudyError("explicit withdrawal and channel required")
        with self._tx() as db:
            self._authenticated(db,ref,token)
            row=db.execute(
                "SELECT email FROM pii.contacts WHERE learner_id=?",(ref,)
            ).fetchone()
            if row is None or not row["email"].lower().endswith(".test"):
                raise SyntheticStudyError("only fictional contact confirmation allowed")
            recipient=row["email"]
            if delete:
                db.execute("INSERT INTO erasure_authorization(one) VALUES(1)")
                try:
                    for name in ("state_history","events","surveys",
                                 "learner_state","sessions"):
                        db.execute(f"DELETE FROM {name} WHERE learner_id=?",(ref,))
                    db.execute("DELETE FROM pii.contacts WHERE learner_id=?",(ref,))
                    db.execute("DELETE FROM participants WHERE learner_id=?",(ref,))
                finally:
                    db.execute("DELETE FROM erasure_authorization")
                db.execute(
                    "INSERT INTO deletion_log(learner_id,deleted_at,channel) "
                    "VALUES(?,?,?)",(ref,iso(at),channel),
                )
            else:
                db.execute(
                    "UPDATE participants SET status='withdrawn',"
                    "status_changed_at=? WHERE learner_id=?",(iso(at),ref),
                )
                db.execute(
                    "UPDATE pii.contacts SET token_hash=? WHERE learner_id=?",
                    (hashlib.sha256(secrets.token_bytes(48)).hexdigest(),ref),
                )
        return {
            "withdrawn":True, "data_deleted":delete,
            "fictional_confirmation_recipient":recipient,
            "real_email_sent":False,"synthetic_only":True,
        }

    def points_export(self) -> list[dict]:
        """Operator-only local export; no participant-facing HTTP endpoint."""
        with self._tx() as db:
            rows=db.execute(
                "SELECT c.email,p.status_changed_at "
                "FROM participants p JOIN pii.contacts c "
                "ON p.learner_id=c.learner_id "
                "WHERE p.status='completed' ORDER BY p.learner_id",
            ).fetchall()
            return [
                {"email":r["email"],"completed_at":r["status_changed_at"]}
                for r in rows if r["email"].lower().endswith(".test")
            ]

    def close_collection(self) -> dict:
        """Wipe fictional PII; separate backup purge must be verified."""
        with self._tx() as db:
            count=db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]
            db.execute("DELETE FROM pii.contacts")
        return {"fictional_contacts_deleted":count,
                "research_preserved":True,"backups_deleted":False,
                "synthetic_only":True}
