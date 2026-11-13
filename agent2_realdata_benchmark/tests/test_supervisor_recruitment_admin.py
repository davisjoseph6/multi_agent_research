"""Offline tests for an isolated recruitment/control-plane prototype.

All applicants are fictional; no email, DNS, VPS or public endpoint is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from src.prototype.supervisor_recruitment import (
    RecruitmentError, RecruitmentLedger, ADMIN_EMAILS,
)
from src.prototype.supervisor_recruitment_web import make_recruitment_app

T=datetime(2026,11,13,13,tzinfo=timezone.utc)
P="A-long-temporary-password-for-tests-001!"
R="A-new-long-personal-password-for-tests-456!"


@pytest.fixture
def ledger(tmp_path):
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    return RecruitmentLedger(private)


def test_candidate_school_external_language_and_private_names(ledger):
    assert ledger.apply(
        email="Person@Aivancity.Education",first_name=" Marie ",
        last_name="L.",questionnaire="school",language="fr",
        privacy_accepted=True,at=T
    ) == {"received":True,"participant_enrolled":False}
    assert ledger.apply(
        email="person@aivancity.education",first_name="Changed",
        questionnaire="school",language="en",
        privacy_accepted=True,at=T
    )["received"]
    assert ledger.apply(
        email="External@example.org",questionnaire="external",
        language="en",privacy_accepted=True,at=T
    )["received"]
    rows=ledger.candidates()
    assert len(rows)==2
    assert rows[1]["first_name"]=="Marie"
    assert rows[1]["last_name"]=="L."
    assert rows[1]["language"]=="fr"
    assert rows[1]["application_count"]==2
    assert len(rows)==2
    assert ledger.file.stat().st_mode&0o077==0
    with pytest.raises(RecruitmentError):
        ledger.apply(email="wrong@example.org",questionnaire="school",
                     language="fr",privacy_accepted=True,at=T)
    with pytest.raises(RecruitmentError):
        ledger.apply(email="student@aivancity.education",
                     questionnaire="external",language="en",
                     privacy_accepted=True,at=T)
    with pytest.raises(RecruitmentError):
        ledger.apply(email="unconsented@example.org",
                     questionnaire="external",language="en",
                     privacy_accepted=False,at=T)
    with pytest.raises(RecruitmentError):
        ledger.apply(email="bad@example.org",questionnaire="external",
                     first_name="<script>",language="en",
                     privacy_accepted=True,at=T)


def test_only_exact_four_accounts_can_be_provisioned(ledger):
    with pytest.raises(RecruitmentError):
        ledger.provision(email="attacker@example.org",
                         temporary_password=P,at=T)
    for address in ADMIN_EMAILS:
        ledger.provision(email=address,temporary_password=P,at=T)
    assert len(ADMIN_EMAILS)==4
    with pytest.raises(RecruitmentError):
        ledger.provision(email="yaacoub@aivancity.ai",
                         temporary_password=R,at=T)


def test_temporary_password_forced_change_and_lockout_persists(ledger):
    email="sara.elkardi@aivancity.education"
    ledger.provision(email=email,temporary_password=P,at=T)
    for i in range(5):
        with pytest.raises(RecruitmentError):
            ledger.login(email=email,password="no",at=T+timedelta(seconds=i))
    with ledger._tx() as db:
        row=db.execute(
            "SELECT failures,locked_until FROM administrators WHERE email=?",
            (email,)
        ).fetchone()
        assert row["failures"]==5 and row["locked_until"]
    with pytest.raises(RecruitmentError):
        ledger.login(email=email,password=P,at=T+timedelta(minutes=5))
    login=ledger.login(email=email,password=P,at=T+timedelta(minutes=16))
    assert login["must_change_password"] is True
    with pytest.raises(RecruitmentError):
        ledger.authenticate(cookie=login["cookie"],
                            csrf=login["csrf"],mutation=True,at=T+timedelta(minutes=17))
    with pytest.raises(RecruitmentError):
        ledger.rotate_password(cookie=login["cookie"],
             csrf="not-correct",current=P,replacement=R,at=T+timedelta(minutes=17))
    ledger.rotate_password(cookie=login["cookie"],csrf=login["csrf"],
                           current=P,replacement=R,at=T+timedelta(minutes=17))
    user=ledger.authenticate(cookie=login["cookie"],
                             csrf=login["csrf"],mutation=True,
                             at=T+timedelta(minutes=18))
    assert user["must_change_password"] is False
    with pytest.raises(RecruitmentError):
        ledger.login(email=email,password=P,at=T+timedelta(minutes=19))
    assert ledger.login(email=email,password=R,at=T+timedelta(minutes=19))
    with pytest.raises(RecruitmentError):
        ledger.authenticate(cookie=login["cookie"],at=T+timedelta(hours=2))


def test_approval_and_reminder_policy_do_not_send_email(ledger):
    ledger.apply(email="one@example.org",questionnaire="external",
                 language="en",privacy_accepted=True,at=T)
    ledger.apply(email="two@example.org",questionnaire="external",
                 language="en",privacy_accepted=True,at=T)
    assert ledger.approve(ids=[1,2],actor="yaacoub@aivancity.ai",at=T)==2
    assert ledger.approve(ids=[1,2],actor="yaacoub@aivancity.ai",at=T)==2
    assert all(row["approved_for_invitation"] for row in ledger.candidates())
    assert ledger.reminder_enabled() is False
    ledger.set_reminder_enabled(
        enabled=True,actor="wiam.belouard@aivancity.education",at=T)
    assert ledger.reminder_enabled() is True
    ledger.set_reminder_enabled(
        enabled=False,actor="wiam.belouard@aivancity.education",at=T)
    assert ledger.reminder_enabled() is False
    with pytest.raises(RecruitmentError):
        ledger.approve(ids=[],actor="yaacoub@aivancity.ai",at=T)


def fake_db(tmp_path):
    research=tmp_path/"research.sqlite3"
    contacts=tmp_path/"contacts.sqlite3"
    with sqlite3.connect(research) as db:
        db.executescript("""
            CREATE TABLE participants(learner_id TEXT,grp TEXT,status TEXT);
            CREATE TABLE learner_state(learner_id TEXT,session_no INTEGER,step TEXT,updated_at TEXT);
            INSERT INTO participants VALUES('STUDY_P001','A','active');
            INSERT INTO learner_state VALUES('STUDY_P001',1,'QUIZ','2026-11-13T13:00:00+00:00');
        """)
    with sqlite3.connect(research) as db:
        db.executescript("""
            CREATE TABLE events(
                event_id INTEGER,learner_id TEXT,session_no INTEGER,
                phase TEXT,question_id TEXT,answered_at TEXT,
                response_time_ms INTEGER,action_type TEXT,is_correct INTEGER
            );
            CREATE TABLE state_history(event_id INTEGER,state_json TEXT);
            INSERT INTO events VALUES
            (1,'STUDY_P001',1,'QUIZ','q1','2026-11-13T13:00:00+00:00',2000,'QUESTION',1),
            (2,'STUDY_P001',1,'QUIZ','q2','2026-11-13T13:00:10+00:00',2400,'QUESTION',0);
        """)
        from src.prototype.supervisor_trace_engine import CONCEPT_IDS
        import json
        for eid,value in ((1,.5),(2,.6)):
            engine=json.dumps({"engine":{"mastery":dict.fromkeys(CONCEPT_IDS,value)}})
            db.execute("INSERT INTO state_history VALUES(?,?)",(eid,engine))
    with sqlite3.connect(contacts) as db:
        db.executescript("""
            CREATE TABLE contacts(learner_id TEXT,email TEXT);
            INSERT INTO contacts VALUES('STUDY_P001','student@example.org');
        """)
    return research,contacts


def test_admin_http_protected_pii_and_bilingual_public_intake(ledger,tmp_path):
    research,contacts=fake_db(tmp_path)
    ledger.provision(email="davis.joseph@aivancity.education",
                     temporary_password=P,at=datetime.now(timezone.utc))
    notices={}
    for language in ("en","fr"):
        notice=tmp_path/f"approved_recruitment_{language}.pdf"
        notice.write_bytes(b"%PDF-1.4\n% fake fictional test-only notice\n")
        notices[language]=notice
    app=make_recruitment_app(
        ledger,public_intake_enabled=True,
        research_db=research,contacts_db=contacts,
        privacy_notices=notices,intake_rate_secret=b"test-only-example-key-"+b"x"*32,
    )
    client=app.test_client()
    def post(path,payload):
        return client.post(path,json=payload,base_url="http://localhost",
                           headers={"Origin":"http://localhost",
                                    "X-Study-Request":"1",
                                    "X-CSRF-Token":client.get_cookie("recruitment_csrf",path="/control/").value
                                        if client.get_cookie("recruitment_csrf",path="/control/") else ""})
    assert client.get("/control/api/overview").status_code==409
    assert client.get("/control/api/candidates").status_code==409
    assert client.get("/interest/school").status_code==200
    assert client.get("/interest/privacy/en").status_code==200
    assert client.get("/interest/privacy/fr").status_code==200
    assert client.get("/interest/external").status_code==200
    assert post("/interest/api/apply",dict(
        email="student@example.org",first_name="Test",last_name="Student",
        questionnaire="external",language="fr",privacy_accepted=True,
    )).status_code==202
    response=post("/control/api/login",dict(
        email="davis.joseph@aivancity.education",password=P))
    assert response.status_code==200,response.json
    assert response.json["must_change_password"]
    assert client.get("/control/api/overview").status_code==409
    assert post("/control/api/change-password",dict(
        current=P,replacement=R)).status_code==200
    candidates=client.get("/control/api/candidates")
    assert candidates.status_code==200
    assert candidates.json["candidates"][0]["first_name"]=="Test"
    overview=client.get("/control/api/overview")
    assert overview.status_code==200,overview.json
    assert overview.json["participants"][0]["email"]=="student@example.org"
    assert overview.json["participants"][0]["first_name"]=="Test"
    assert overview.json["participants"][0]["step"]=="QUIZ"
    mastery=client.get("/control/api/mastery/STUDY_P001")
    assert mastery.status_code==200,mastery.json
    assert mastery.json["email"]=="student@example.org"
    assert mastery.json["first_name"]=="Test"
    assert len(mastery.json["points"])==2
    timing=client.get("/control/api/question-intervals?learner_id=STUDY_P001")
    assert timing.status_code==200,timing.json
    assert len(timing.json["intervals"])==2
    assert timing.json["intervals"][1]["between_answers_seconds"]==10
    assert post("/control/api/send-invitations",
                {"candidate_ids":[1],"select_all":False}).status_code==409
    assert post("/control/api/approve",{"candidate_ids":[1]}).json=={
        "approved":1,"email_sent":False
    }
    assert post("/control/api/reminder-policy",{"enabled":True}).status_code==200
    assert client.get("/control/api/reminder-policy").json["automatic_reminders_enabled"]
    assert client.get("/control/app.js").status_code==200
    assert client.get("/control/app.css").status_code==200


def test_intake_disabled_by_default_and_browser_origin_enforced(ledger):
    app=make_recruitment_app(ledger)
    client=app.test_client()
    assert client.get("/interest/school").status_code==404
    assert client.get("/interest/external").status_code==404
    assert client.post("/interest/api/apply",json={},
                       headers={"Origin":"http://localhost",
                                "X-Study-Request":"1"}).status_code==404
    assert client.post("/control/api/login",json={},
                       headers={"Origin":"https://evil.example",
                                "X-Study-Request":"1"}).status_code==403


def test_graph_outlook_sender_requires_signed_release_and_scope():
    import json
    from urllib.parse import parse_qs
    from src.prototype.supervisor_graph_mail import GraphMailSender,GraphMailError
    calls=[]
    def http(url,*,data,headers,timeout):
        calls.append((url,data,headers))
        if "oauth2/v2.0/token" in url:
            assert parse_qs(data.decode())["scope"]==[
                "https://graph.microsoft.com/.default"]
            return (200,b'{"access_token":"dummy-totally-fictional-access-token"}')
        assert url.endswith("/users/davis.joseph@aivancity.education/sendMail")
        assert headers["Authorization"].startswith("Bearer dummy-totally")
        body=json.loads(data)
        assert body["message"]["toRecipients"][0]["emailAddress"]["address"]=="fake@example.org"
        assert body["message"]["subject"]=="Test invitation"
        return (202,b"")
    kwargs=dict(tenant_id="01234567-89ab-cdef-0123-456789abcdef",
                client_id="12345678-1234-1234-1234-123456789abc",
                client_secret="example-client-secret-not-real",
                sender_email="davis.joseph@aivancity.education",transport=http)
    with pytest.raises(GraphMailError,match="signed institutional"):
        GraphMailSender(**kwargs)
    sender=GraphMailSender(**kwargs,live_release_verified=True)
    sender.send(to="FAKE@example.org",subject="Test invitation",body="Hello")
    assert len(calls)==2
    with pytest.raises(GraphMailError,match="content"):
        sender.send(to="fake@example.org",subject="Bad\r\nSubject",body="body")
    assert len(calls)==2


def test_decimal_time_intervals_include_breaks_not_just_response_latency(tmp_path):
    from src.prototype.supervisor_recruitment_metrics import inter_answer_times
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.executescript("""
      CREATE TABLE events(
       event_id INTEGER PRIMARY KEY,learner_id TEXT,session_no INTEGER,
       phase TEXT,question_id TEXT,answered_at TEXT,
       response_time_ms INTEGER,action_type TEXT);
      INSERT INTO events VALUES
        (1,'STUDY_P001',1,'PRETEST','a','2026-11-13T13:00:00+00:00',1500,'QUESTION'),
        (2,'STUDY_P001',1,'QUIZ',NULL,'2026-11-13T13:00:03+00:00',1200,'CONCEPT_SUMMARY'),
        (3,'STUDY_P001',1,'QUIZ','b','2026-11-13T14:00:01+00:00',2000,'QUESTION'),
        (4,'STUDY_P001',1,'QUIZ','c','2026-11-14T14:00:01+00:00',2100,'QUESTION');
    """)
    rows=inter_answer_times(db,learner_id="STUDY_P001")
    assert len(rows)==3
    assert rows[0]["between_answers_seconds"] is None
    assert rows[1]["between_answers_seconds"]==3601
    assert rows[1]["between_answers_ms"]==3601000
    assert rows[1]["between_answers_hours"]==round(3601/3600,9)
    assert rows[2]["between_answers_days"]==1
    assert rows[1]["response_latency_ms"]==2000
    assert rows[1]["includes_breaks_and_interventions"] is True
    db.close()


def test_three_four_seven_day_idle_policy_and_session_waiting():
    from src.prototype.supervisor_inactivity_policy import (
        evaluate_inactivity,make_reminder_text,
    )
    last=T
    def check(days,**changes):
        args=dict(now=T+timedelta(days=days),last_active=last,phase="QUIZ",
                  session=2,status="active",locale="en",automatic_enabled=True)
        args.update(changes)
        return evaluate_inactivity(**args)
    assert not check(2.9)["send"]
    assert check(3)["reason"]=="automatic_three_day_encouragement"
    assert check(3,automatic_enabled=False)["send"] is False
    assert check(4,automatic_enabled=False,manual_requested=True)["send"]
    assert not check(4,manual_requested=True,
                     last_reminder=T+timedelta(days=3.5))["send"]
    assert not check(5,last_reminder=T+timedelta(days=3))["send"]
    assert check(6,last_reminder=T+timedelta(days=3))["send"]
    assert check(7)["expired"] and not check(7)["send"]
    assert not check(100,phase="WAITING_NEXT_SESSION")["expired"]
    assert not check(100,phase="DONE")["expired"]
    assert not check(100,status="withdrawn")["expired"]
    assert "learning quiz" in make_reminder_text(
        session=2,phase="QUIZ",language="en")
    assert "quiz d’apprentissage" in make_reminder_text(
        session=2,phase="QUIZ",language="fr")


def test_rate_limit_keeps_raw_ip_private_and_rejects_abuse(ledger):
    for n in range(10):
        assert ledger.check_intake_rate(
            remote_ip="192.0.2.5",secret=b"x"*32,at=T,
        )
    assert ledger.check_intake_rate(
        remote_ip="192.0.2.5",secret=b"x"*32,at=T,
    ) is False
    assert ledger.check_intake_rate(
        remote_ip="192.0.2.6",secret=b"x"*32,at=T,
    ) is True
    with ledger._tx() as db:
        values=[dict(r) for r in db.execute("SELECT * FROM intake_rate")]
    assert "192.0.2.5" not in repr(values)
    assert ledger.check_intake_rate(
        remote_ip="192.0.2.5",secret=b"x"*32,at=T+timedelta(days=1),
    ) is True
