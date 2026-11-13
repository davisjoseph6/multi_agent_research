"""Security and durable-sessions acceptance for the separate /study/ VPS app.

Never sends SMTP, never uses a real address, never authorizes human enrollment.
Only reserved *.example identities are issued via an offline operation.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)
from src.prototype.supervisor_vps_web import make_supervisor_vps_app

BANK=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
NOW=lambda:datetime.now(timezone.utc)
BASE="http://127.0.0.1:8788"


def stack(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(BANK),
                                   operational=True)
    intake=OperationalIntake(store,programs=("Test student program",))
    app=make_supervisor_vps_app(
        intake,hostname="demo.selfhealing-edu.fr",proxy_mode=False,
        release_mode="staging",
    )
    client=app.test_client()
    def post(endpoint,value=None,*,origin=BASE,csrf=True,base=BASE):
        headers={"Origin":origin,"Content-Type":"application/json"}
        if csrf:headers["X-Study-Request"]="1"
        return client.post("/study/api/"+endpoint,
                           json=value if value is not None else {},
                           headers=headers,base_url=base)
    return store,intake,client,post


def complete_intake(intake,store,token,*,at=None):
    at=at or NOW()
    intake.consent(token,checks=[True]*5,optional=False,language="en",at=at)
    answers={
        q.question_id:(q.correct_answer if i<4 else next(
            k for k in "ABCD" if k!=q.correct_answer))
        for i,q in enumerate(store.bank.forms["screening"])
    }
    assert intake.screening(token,answers=answers,at=at)["eligible"]
    return intake.register(token,age=24,program="Test student program",at=at)


def test_operational_mode_keeps_synthetic_databases_and_identity_separate(tmp_path):
    synthetic=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(BANK))
    operational=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(BANK),
                                         operational=True)
    assert synthetic.research!=operational.research
    assert synthetic.contacts!=operational.contacts
    assert synthetic.research.exists() and operational.research.exists()
    with pytest.raises(SyntheticStudyError,match="test contacts"):
        operational_issue=OperationalIntake(operational,programs=("Test student program",))
        operational_issue.issue("someone@example.test",at=NOW(),allow_example=True)
    with pytest.raises(SyntheticStudyError,match="reserved"):
        operational_issue.issue("real@gmail.com",at=NOW(),allow_example=True)


def test_human_release_never_enables_from_constructor_flag(tmp_path):
    store,intake,_,_=stack(tmp_path)
    with pytest.raises(ValueError,match="independently verified"):
        make_supervisor_vps_app(
            intake,hostname="demo.selfhealing-edu.fr",
            proxy_mode=False,release_mode="live",
        )


def test_invitation_verification_and_csrf_host_isolation(tmp_path):
    _,intake,client,post=stack(tmp_path)
    token=intake.issue("test-f1@example.example",at=NOW(),allow_example=True)
    denied=post("status")
    assert denied.status_code==409
    denied=post("exchange",{"token":token},origin="http://evil.invalid")
    assert denied.status_code==403
    denied=post("exchange",{"token":token},csrf=False)
    assert denied.status_code==403
    denied=post("exchange",{"token":token},base="http://evil.invalid:8788",
                origin="http://evil.invalid:8788")
    assert denied.status_code==403
    response=post("exchange",{"token":token})
    assert response.status_code==200,response.json
    assert response.json["stage"]=="invited"
    cookies="; ".join(response.headers.getlist("Set-Cookie"))
    assert "HttpOnly" in cookies and "SameSite=Strict" in cookies
    assert "Path=/study/" in cookies
    assert token not in response.get_data(as_text=True)
    assert post("status").json["stage"]=="invited"
    assert client.get("/study/",base_url=BASE).status_code==200
    assert client.get("/study/app.js",base_url=BASE).status_code==200
    assert client.get("/study/app.css",base_url=BASE).status_code==200
    assert client.get("/study/health",base_url=BASE).json["enrollment_authorized"] is False


def test_registration_persistence_and_assessment_feedback_separation(tmp_path):
    store,intake,_,post=stack(tmp_path)
    token=intake.issue("test-f1@example.example",at=NOW(),allow_example=True)
    assert post("exchange",{"token":token}).status_code==200
    assert len(post("consent-copy",{"language":"fr"}).json["required"])==5
    assert post("consent",{"checks":[True]*4+[False],
                           "optional":False,"language":"fr"}).status_code==409
    assert post("consent",{"checks":[True]*5,"optional":False,
                           "language":"fr"}).status_code==200
    screening=post("screening").json
    assert len(screening["questions"])==8
    assert screening["language"]=="fr"
    answers={
        q.question_id:(q.correct_answer if i<4 else next(
            k for k in "ABCD" if k!=q.correct_answer))
        for i,q in enumerate(store.bank.forms["screening"])
    }
    assert post("screen",{"answers":answers}).json["eligible"]
    assert post("programs").json["programs"]==["Test student program"]
    response=post("register",{"age":24,"program":"Test student program"})
    assert response.status_code==200,response.json
    assert response.json["phase"]=="PRETEST"
    status=post("status").json
    assert status["study_language"]=="fr"
    assert "group" not in status and "learner_id" not in status
    item=post("item").json
    assert item["phase"]=="PRETEST"
    answer=store.bank.forms["pretest"][0]
    assert item["question_id"]==answer.question_id
    response=post("answer",{
        "render_id":item["render_id"],"question_id":item["question_id"],
        "choice":answer.correct_answer,"reflection":None,
        "request_id":"test_vps_first_pretest",
    })
    assert response.status_code==200,response.json
    assert "previous_correct" not in response.json
    assert post("answer",{
        "render_id":item["render_id"],"question_id":item["question_id"],
        "choice":answer.correct_answer,"reflection":None,
        "request_id":"test_vps_first_pretest",
    }).status_code==409
    with store._tx() as db:
        row=db.execute("SELECT display_language FROM events WHERE request_id=?",
                       ("test_vps_first_pretest",)).fetchone()
        assert row["display_language"]=="fr"
        contact=db.execute("SELECT email FROM pii.contacts").fetchone()
        assert contact["email"]=="test-f1@example.example"

    # Recreate the WSGI application, as a production restart would do.
    store2,intake2,client2,post2=stack(tmp_path)
    assert post2("exchange",{"token":token}).status_code==200
    continued=post2("item").json
    assert continued["question_id"]==store.bank.forms["pretest"][1].question_id
    assert continued["question_text"]!=store.bank.forms["pretest"][1].question_text
    assert continued["render_id"]!=item["render_id"]


def test_allocation_and_irreversible_erasure(tmp_path):
    store,intake,_,post=stack(tmp_path)
    ids=[]
    for n in (1,2,3):
        token=intake.issue(f"test-f{n}@example.example",
                           at=NOW(),allow_example=True)
        complete_intake(intake,store,token)
        ids.append((token,intake.learner(token,at=NOW())))
    with store._tx() as db:
        arms=[db.execute("SELECT grp FROM participants WHERE learner_id=?",
                         (ref,)).fetchone()["grp"] for _,ref in ids]
    assert arms==["A","B","C"]
    first,ref=ids[0]
    post("exchange",{"token":first})
    presented=post("item").json
    assert presented["render_id"]
    deleted=post("withdraw",{"delete":True})
    assert deleted.status_code==200,deleted.json
    assert deleted.json["data_deleted"]
    assert post("status").status_code==409
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.invitations "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM operational_rendered "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM deletion_log "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]==1


def test_screening_exclusion_has_no_recruitment_pii(tmp_path):
    store,intake,_,post=stack(tmp_path)
    token=intake.issue("excluded@example.example",at=NOW(),allow_example=True)
    assert post("exchange",{"token":token}).status_code==200
    assert post("consent",{"checks":[True]*5,"optional":False,
                           "language":"en"}).status_code==200
    answers={q.question_id:q.correct_answer for q in store.bank.forms["screening"]}
    response=post("screen",{"answers":answers})
    assert response.status_code==200 and response.json["eligible"] is False
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM pii.invitations").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM screening_log").fetchone()[0]==1
    assert post("status").status_code==409


def test_offline_verified_withdrawal_and_collection_close_gate(tmp_path):
    store,intake,_,_=stack(tmp_path)
    token=intake.issue("offline@example.example",at=NOW(),allow_example=True)
    complete_intake(intake,store,token)
    ref=intake.learner(token,at=NOW())
    with pytest.raises(SyntheticStudyError,match="remain active"):
        store.close_collection()
    result=store.offline_admin_withdraw(
        ref,delete=True,channel="email",at=NOW(),
    )
    assert result["withdrawn"] and result["data_deleted"]
    with store._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM participants WHERE learner_id=?",(ref,)
        ).fetchone()[0]==0
        assert db.execute(
            "SELECT COUNT(*) FROM pii.invitations WHERE learner_id=?",(ref,)
        ).fetchone()[0]==0
        assert db.execute(
            "SELECT COUNT(*) FROM deletion_log WHERE learner_id=?",(ref,)
        ).fetchone()[0]==1
    assert store.close_collection()["research_preserved"]


def test_supervisor_staging_review_advances_only_fictional_waiting_visits(tmp_path):
    """Reviewers can test visits 2/3 tonight without weakening live scheduling."""
    import json
    from src.prototype.supervisor_trace_engine import SupervisorTraceEngine, CONCEPT_IDS

    store, intake, _, post = stack(tmp_path)
    token = intake.issue("review-case@example.example",
                         at=NOW(), allow_example=True)
    complete_intake(intake, store, token)
    ref = intake.learner(token, at=NOW())
    assert post("exchange", {"token": token}).status_code == 200

    # Never skip consent, screening, pretest, or an active quiz.
    assert post("staging-next-session").status_code == 409

    # The normal study endpoint must still reject early entry.
    with store._tx() as db:
        row = db.execute("SELECT state_json FROM learner_state "
                         "WHERE learner_id=?", (ref,)).fetchone()
        state = json.loads(row["state_json"])
        state["phase"] = "WAITING_NEXT_SESSION"
        state["session"] = 1
        engine = SupervisorTraceEngine("A", dict.fromkeys(CONCEPT_IDS, .5))
        # Fabricate a completed test block, never bypass that invariant.
        engine.question_in_session = 20
        state["engine"] = engine.snapshot()
        db.execute("UPDATE learner_state SET step='WAITING_NEXT_SESSION',"
                   "step_index=0,state_json=? WHERE learner_id=?",
                   (json.dumps(state), ref))
        scheduled = db.execute(
            "SELECT scheduled_for FROM sessions "
            "WHERE learner_id=? AND session_no=2", (ref,)
        ).fetchone()[0]

    assert scheduled > NOW().isoformat()
    assert post("next-session").status_code == 409
    started = post("staging-next-session")
    assert started.status_code == 200, started.json
    assert started.json["session_started"] == 2
    assert started.json["staging_preview_advance"] is True
    assert post("status").json["session"] == 2
    assert post("staging-next-session").status_code == 409

    with store._tx() as db:
        session = db.execute("SELECT scheduled_for,status FROM sessions "
                             "WHERE learner_id=? AND session_no=2",
                             (ref,)).fetchone()
        assert session["status"] == "in_progress"
        assert session["scheduled_for"] <= NOW().isoformat()
        contact = db.execute("SELECT email FROM pii.contacts "
                             "WHERE learner_id=?", (ref,)).fetchone()
        assert contact["email"] == "review-case@example.example"


def test_live_api_does_not_register_staging_review_route(tmp_path):
    store, intake, _, _ = stack(tmp_path)
    # Constructor release flag is a unit-test fixture, not release evidence.
    live_app = make_supervisor_vps_app(
        intake, hostname="demo.selfhealing-edu.fr", proxy_mode=False,
        release_mode="live", release_authorized=True,
    )
    client = live_app.test_client()
    denied = client.post("/study/api/staging-next-session", json={},
                         base_url=BASE,
                         headers={"Origin": BASE, "X-Study-Request": "1"})
    assert denied.status_code == 404


def test_post_answer_quiz_feedback_and_preserved_display_time(tmp_path):
    """Correct answer is unavailable before submission or during pretest."""
    store,intake,_,post=stack(tmp_path)
    token=intake.issue("screen-safe@example.example",at=NOW(),allow_example=True)
    complete_intake(intake,store,token)
    assert post("exchange",{"token":token}).status_code==200

    first=post("item").json
    again=post("item").json
    assert first["render_id"]==again["render_id"], "refresh reset response timer"
    assert "correct_choice" not in first
    assert "explanation" not in first
    assert post("session-summary").json["sessions"]==[]

    for index in range(16):
        q=post("item").json
        assert q["kind"]=="question" and q["phase"]=="PRETEST"
        answer=store.bank.get(q["question_id"],form="pretest").correct_answer
        result=post("answer",dict(
            render_id=q["render_id"],request_id=f"pre_item_{index:03d}",
            question_id=q["question_id"],choice=answer,reflection=None,
        ))
        assert result.status_code==200,result.json
        assert "previous_correct" not in result.json
        assert "correct_choice" not in result.json
        assert "explanation" not in result.json

    quiz=post("item").json
    assert quiz["action"]=="QUESTION"
    assert "correct_choice" not in quiz and "explanation" not in quiz
    key=store.bank.get(quiz["question_id"],form="practice").correct_answer
    result=post("answer",dict(
        render_id=quiz["render_id"],request_id="review_quiz_001",
        question_id=quiz["question_id"],choice=key,reflection=None,
    ))
    assert result.status_code==200,result.json
    assert result.json["feedback_phase"]=="QUIZ"
    assert result.json["previous_correct"] is True
    assert result.json["correct_choice"]==key
    assert result.json["explanation"]==store.bank.get(
        quiz["question_id"],form="practice"
    ).explanation
    assert result.json["explanation_language"]=="en"
    assert post("session-summary").json["sessions"]==[]
    # The same item can never be graded twice by replay.
    assert post("answer",dict(
        render_id=quiz["render_id"],request_id="review_quiz_001",
        question_id=quiz["question_id"],choice=key,reflection=None,
    )).status_code==409


def test_staging_logo_falls_back_when_png_not_committed(tmp_path):
    _,_,client,_=stack(tmp_path)
    response=client.get("/study/logo.png",base_url=BASE)
    assert response.status_code in (200,404)
    if response.status_code==200:
        assert response.mimetype=="image/png"


def test_mid_screening_language_override_preserves_signed_consent(tmp_path):
    """Signed consent stays French; questions may display in English.
    
    The locale-only endpoint never scores, changes an item ID, or accepts a
    client's proposal for the current screening question or answer keys.
    """
    store,intake,_,post=stack(tmp_path)
    token=intake.issue("switch-screen@example.example",at=NOW(),allow_example=True)
    assert post("exchange",{"token":token}).status_code==200
    assert post("consent",{"checks":[True]*5,"optional":False,
                           "language":"fr"}).status_code==200
    fr=post("screening").json
    assert fr["language"]=="fr"
    en_result=post("screening",{"language":"en"})
    assert en_result.status_code==200,en_result.json
    en=en_result.json
    assert en["language"]=="en"
    assert [q["question_id"] for q in fr["questions"]]==[
        q["question_id"] for q in en["questions"]]
    assert fr["questions"][2]["question_text"]!=en["questions"][2]["question_text"]
    assert set(fr["questions"][2]["options"])==set(en["questions"][2]["options"])
    assert post("status").json["stage"]=="consented"
    assert post("status").json["language"]=="fr"
    for invalid in ({"language":"de"},{"language":""},{"language":1},
                    {"language":"en","index":0},{"index":0}):
        assert post("screening",invalid).status_code==409
    assert post("screening",{"language":"fr"}).json["questions"]==fr["questions"]

    answers={
        q.question_id:(q.correct_answer if i<4 else next(
            a for a in "ABCD" if a!=q.correct_answer))
        for i,q in enumerate(store.bank.forms["screening"])
    }
    assert post("screen",{"answers":answers}).json["eligible"]
    assert post("register",{"age":23,"program":"Test student program"}).status_code==200
    assert post("language",{"language":"en"}).status_code==200
    assert post("status").json["study_language"]=="en"
    ref=intake.learner(token,at=NOW())
    with store._tx() as db:
        row=db.execute("SELECT consent_lang,study_language FROM participants "
                       "WHERE learner_id=?",(ref,)).fetchone()
    assert (row["consent_lang"],row["study_language"])==("fr","en")


def test_mid_question_language_change_preserves_render_credential(tmp_path):
    """A translated pre-test item is the same measured exposure."""
    store,intake,_,post=stack(tmp_path)
    token=intake.issue("switch-render@example.example",at=NOW(),allow_example=True)
    complete_intake(intake,store,token)
    assert post("exchange",{"token":token}).status_code==200
    first=post("item").json
    assert post("language",{"language":"fr"}).status_code==200
    french=post("item").json
    assert first["question_id"]==french["question_id"]
    assert first["render_id"]==french["render_id"]
    assert first["question_text"]!=french["question_text"]
    assert post("language",{"language":"en"}).status_code==200
    assert post("item").json["render_id"]==first["render_id"]


def test_read_only_database_preflight_never_discloses_contact_or_tokens(tmp_path):
    from scripts.supervisor_staging_db_preflight import inspect_state
    import json
    store,intake,_,_=stack(tmp_path)
    token=intake.issue("private-preflight@example.example",at=NOW(),
                       allow_example=True)
    first=inspect_state(tmp_path)
    assert first["passed"]
    assert first["unclaimed_invitation_count"]==1
    assert not first["real_human_recruitment_approved"]
    complete_intake(intake,store,token)
    second=inspect_state(tmp_path)
    assert second["passed"]
    assert second["allocation_counts_by_arm"]=={"A":1}
    assert second["unclaimed_invitation_count"]==0
    assert second["mutated_database"] is False
    output=json.dumps(second)
    assert "private-preflight@example.example" not in output
    assert token not in output
    assert "token_hash" not in output


def test_read_only_database_preflight_fails_on_contact_hash_mismatch(tmp_path):
    from scripts.supervisor_staging_db_preflight import inspect_state
    store,intake,_,_=stack(tmp_path)
    token=intake.issue("inconsistent@example.example",at=NOW(),allow_example=True)
    complete_intake(intake,store,token)
    with store._tx() as db:
        db.execute("UPDATE pii.contacts SET token_hash=?",
                   ("0"*64,))
    status=inspect_state(tmp_path)
    assert status["passed"] is False
    assert status["technical_db_checks"]["registered_token_hashes_match"] is False
    assert status["contains_identifying_contact_details"] is False
