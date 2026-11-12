"""No-human synthetic localization and practice-feedback acceptance, all arms."""
from datetime import timedelta
from pathlib import Path
import json
import re

from scripts.supervisor_fictional_browser import new_supervisor_fictional_runtime
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_i18n import (
    french_bank, localize_public, validate_french_bank,
)
from src.prototype.supervisor_recovery_content import recovery_resource
from src.prototype.supervisor_fictional_web import make_supervisor_fictional_app

PORT=8783
BASE=f"http://127.0.0.1:{PORT}"
DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


def harness(tmp_path):
    runtime=new_supervisor_fictional_runtime(tmp_path)
    app=make_supervisor_fictional_app(runtime,port=PORT)
    client=app.test_client()
    html=client.get("/",base_url=BASE).get_data(as_text=True)
    nonce=re.search(r'data-preview-nonce="([^"]+)"',html).group(1)
    def post(route,data=None,fixture="F1"):
        return client.post(
            "/supervisor/api/"+route,
            json={"fixture":fixture,**(data or {})},
            headers={"X-Preview-Nonce":nonce,"Origin":BASE},
            base_url=BASE,
        )
    return runtime,client,post


def fake_enroll(runtime, fixture):
    bank=runtime.store.bank
    answers={
        q.question_id:(q.correct_answer if i<4 else next(
            letter for letter in "ABCD" if letter!=q.correct_answer
        ))
        for i,q in enumerate(bank.forms["screening"])
    }
    result=runtime.store.register(
        contact_email=f"unit-{fixture.lower()}@example.test",
        econ_course=False,screening_answers=answers,
        consent_version="v1.0-fictional",consent_given=True,
        age=23,program="Synthetic classroom demonstration",
        at=runtime.clock(),
    )
    assert result["eligible"]
    runtime.roster[fixture]=(
        result["fictional_learner_id"],result["fictional_private_token"],
    )
    return runtime.roster[fixture]


def finish_pretest(runtime, fixture):
    ref,token=runtime.roster[fixture]
    for index,q in enumerate(runtime.store.bank.forms["pretest"]):
        instant=runtime.clock()
        runtime.store.answer_assessment(
            ref,token,request_id=f"{fixture}_test_pre_{index:02d}",
            item_id=q.question_id,choice=q.correct_answer,
            shown_at=instant,answered_at=instant+timedelta(milliseconds=2),
        )
    assert runtime.store.progress(ref,token)["phase"]=="QUIZ"


def test_every_french_question_and_option_is_present_and_preserves_keys():
    bank=SupervisorBank(DATA)
    validate_french_bank(bank)
    assert len(french_bank())==232
    for identifier,item in bank.by_id.items():
        localized=localize_public(item.public(),language="fr")
        assert localized["question_id"]==identifier
        assert localized["question_text"]!=item.question_text
        assert set(localized["options"])==set("ABCD")
        assert all(localized["options"].values())
        assert item.correct_answer in localized["options"]


def test_all_recovery_resources_are_french_and_unicode():
    for concept_index in range(1,9):
        concept=f"C{concept_index}"
        for action in ("CONCEPT_SUMMARY","WORKED_EXAMPLE","SOCRATIC_HINT"):
            item=recovery_resource(
                concept,action,language="fr",
                question_text="Quel choix reflète le concept ?" if action=="SOCRATIC_HINT" else None,
            )
            assert item["language"]=="fr"
            assert item["content_id"].endswith("_fr")
            assert item["review_status"].startswith("DRAFT")
            text=" ".join(item.get("paragraphs",item.get("prompts",[])))
            assert len(text)>100


def test_browser_screening_pretest_and_switch_to_french(tmp_path):
    runtime,client,post=harness(tmp_path)
    consent=post("consent/start",{
        "checks":[True]*6,"optional":False,"language":"fr",
    })
    assert consent.status_code==200,consent.json
    screening=post("screening").json
    assert screening["language"]=="fr"
    q=screening["questions"][0]
    assert "économie" in q["question_text"]
    original=runtime.store.bank.forms["screening"][0]
    assert q["question_id"]==original.question_id
    assert q["options"]["B"]!=original.options[1]

    answers={
        item.question_id:(
            item.correct_answer if i<4 else next(
                x for x in "ABCD" if x!=item.correct_answer
            )
        )
        for i,item in enumerate(runtime.store.bank.forms["screening"])
    }
    assert post("consent/screen",{"answers":answers}).json["eligible"]
    registered=post("consent/register",{
        "email":"french-user@example.test","age":23,
        "program":"Synthetic classroom demonstration",
    })
    assert registered.status_code==200,registered.json
    assert post("status").json["study_language"]=="fr"
    p=post("item").json
    assert p["phase"]=="PRETEST"
    assert p["question_text"]!=runtime.store.bank.forms["pretest"][0].question_text

    # The same exact question ID is served after changing languages.
    assert post("language",{"language":"en"}).status_code==200
    english=post("item").json
    assert english["question_id"]==p["question_id"]
    assert english["question_text"]==runtime.store.bank.forms["pretest"][0].question_text
    assert post("language",{"language":"fr"}).status_code==200

    # The study language is separate from legal consent language and persists.
    ref,token=runtime.roster["F1"]
    with runtime.store._tx() as db:
        row=db.execute(
            "SELECT consent_lang,study_language FROM participants WHERE learner_id=?",
            (ref,),
        ).fetchone()
    assert (row["consent_lang"],row["study_language"])==("fr","fr")

    before=post("item").json
    q=runtime.store.bank.forms["pretest"][0]
    outcome=post("answer",{
        "question_id":q.question_id,"choice":q.correct_answer,
        "request_id":"french_assessment_no_feedback",
    })
    assert outcome.status_code==200
    assert "previous_correct" not in outcome.json
    after=post("item").json
    assert after["question_id"]!=before["question_id"]
    assert after["question_text"]!=runtime.store.bank.forms["pretest"][1].question_text


def test_all_three_arms_provide_boolean_feedback_only_after_quiz_commit(tmp_path):
    runtime,_,post=harness(tmp_path)
    for fixture in ("F1","F2","F3"):
        fake_enroll(runtime,fixture)
        finish_pretest(runtime,fixture)
    for fixture,expected_arm in zip(("F1","F2","F3"),("A","B","C")):
        ref,token=runtime.roster[fixture]
        with runtime.store._tx() as db:
            arm=db.execute("SELECT grp FROM participants WHERE learner_id=?",
                           (ref,)).fetchone()["grp"]
        assert arm==expected_arm
        current=post("item",fixture=fixture).json
        answer=runtime.store.bank.get(current["question_id"],form="practice")
        response=post("answer",{
            "question_id":current["question_id"],
            "choice":answer.correct_answer,
            "request_id":f"right_{fixture}_question",
        },fixture=fixture)
        assert response.status_code==200,response.json
        assert response.json["previous_correct"] is True
        assert response.json["feedback_phase"]=="QUIZ"
        current=post("item",fixture=fixture).json
        answer=runtime.store.bank.get(current["question_id"],form="practice")
        wrong=next(letter for letter in "ABCD" if letter!=answer.correct_answer)
        response=post("answer",{
            "question_id":current["question_id"],
            "choice":wrong,
            "request_id":f"wrong_{fixture}_question",
        },fixture=fixture)
        assert response.status_code==200,response.json
        assert response.json["previous_correct"] is False
        assert "correct_answer" not in str(response.json)


def test_french_reflections_are_stored_without_corruption(tmp_path):
    runtime,_,post=harness(tmp_path)
    assert post("demo/prime-recovery").status_code==200
    assert post("language",{"language":"fr"}).status_code==200
    for index in range(3):
        item=post("item").json
        assert item["language"]=="fr"
        qid=item.get("question_id")
        if qid:
            answer=runtime.store.bank.get(qid,form="practice")
            choice=answer.correct_answer
        else:
            choice=None
        response=post("answer",{
            "question_id":qid,"choice":choice,
            "request_id":f"french_recovery_{index:02d}",
        })
        assert response.status_code==200,response.json

    socratic=post("item").json
    assert socratic["action"]=="SOCRATIC_HINT"
    assert socratic["language"]=="fr"
    assert "perte" in " ".join(socratic["resource"]["prompts"])
    reflection=[
        "J'examine les pertes et les gains à partir d'un point de référence.",
        "Une perte égale à un gain peut provoquer une émotion plus forte : c'est l'aversion.",
    ]
    qid=socratic["question_id"]
    correct=runtime.store.bank.get(qid,form="practice").correct_answer
    submit=post("answer",{
        "question_id":qid,"choice":correct,
        "reflection":reflection,"request_id":"accented_reflections_001",
    })
    assert submit.status_code==200,submit.json
    assert submit.json["previous_correct"] is True
    with runtime.store._tx() as db:
        row=db.execute(
            "SELECT free_text FROM events WHERE action_type='SOCRATIC_HINT' "
            "ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
    assert json.loads(row["free_text"])==reflection


def test_static_bilingual_ui_and_feedback_contract(tmp_path):
    _,client,_=harness(tmp_path)
    html=client.get("/",base_url=BASE).get_data(as_text=True)
    assert 'id="study-lang"' in html
    assert 'id="previous-result"' in html
    for url in ("/supervisor-copy.js","/supervisor-fake.js"):
        r=client.get(url,base_url=BASE)
        assert r.status_code==200
    copy=client.get("/supervisor-copy.js",base_url=BASE).get_data(as_text=True)
    code=client.get("/supervisor-fake.js",base_url=BASE).get_data(as_text=True)
    assert "Previous answer was correct" in copy
    assert "La réponse précédente était incorrecte" in copy
    assert "renderPreviousFeedback" in code
    assert 'call("language",{language:chosen})' in code


def test_each_arm_retains_the_last_quiz_feedback_when_entering_survey(tmp_path):
    """All 20 graded quiz answers, including the last, return correctness."""
    runtime,_,post=harness(tmp_path)
    for fixture in ("F1","F2","F3"):
        fake_enroll(runtime,fixture)
        finish_pretest(runtime,fixture)
    for fixture in ("F1","F2","F3"):
        ref,token=runtime.roster[fixture]
        final_response=None
        for number in range(20):
            current=runtime.store.next_item(ref,token)
            assert current["kind"]=="question" and current["action"]=="QUESTION"
            correct=runtime.store.bank.get(
                current["question_id"],form="practice"
            ).correct_answer
            instant=runtime.clock()
            final_response=runtime.store.answer_quiz(
                ref,token,request_id=f"final_{fixture}_{number:02d}",
                item_id=current["question_id"],choice=correct,
                shown_at=instant,answered_at=instant+timedelta(milliseconds=2),
            )
            assert final_response["previous_correct"] is True
        assert runtime.store.progress(ref,token)["phase"]=="SURVEY"
        assert final_response["feedback_phase"]=="QUIZ"
        # The browser must retain the final result while showing the survey.


def test_events_pin_each_display_language_after_mid_session_switch(tmp_path):
    runtime,_,post=harness(tmp_path)
    fake_enroll(runtime,"F1")
    finish_pretest(runtime,"F1")
    ref,token=runtime.roster["F1"]
    assert post("language",{"language":"fr"}).status_code==200
    current=post("item").json
    assert current["language"]=="fr"
    correct=runtime.store.bank.get(current["question_id"],form="practice").correct_answer
    result=post("answer",{
        "question_id":current["question_id"],"choice":correct,
        "request_id":"lang_event_fr_001",
    })
    assert result.status_code==200,result.json

    assert post("language",{"language":"en"}).status_code==200
    next_question=post("item").json
    assert next_question["language"]=="en"
    correct=runtime.store.bank.get(
        next_question["question_id"],form="practice"
    ).correct_answer
    result=post("answer",{
        "question_id":next_question["question_id"],"choice":correct,
        "request_id":"lang_event_en_001",
    })
    assert result.status_code==200,result.json

    with runtime.store._tx() as db:
        events=db.execute(
            "SELECT request_id,display_language FROM events "
            "WHERE request_id IN ('lang_event_fr_001','lang_event_en_001')"
            " ORDER BY event_id",
        ).fetchall()
        participant=db.execute(
            "SELECT consent_lang,study_language FROM participants "
            "WHERE learner_id=?",(ref,)
        ).fetchone()
    assert [(e["request_id"],e["display_language"]) for e in events]==[
        ("lang_event_fr_001","fr"),("lang_event_en_001","en")
    ]
    assert participant["study_language"]=="en"  # mutable, not event history


def test_french_recovery_event_content_id_matches_displayed_version(tmp_path):
    runtime,_,post=harness(tmp_path)
    assert post("demo/prime-recovery").status_code==200
    assert post("language",{"language":"fr"}).status_code==200
    text=post("item").json
    assert text["action"]=="CONCEPT_SUMMARY"
    assert text["resource"]["content_id"].endswith("_fr")
    assert post("answer",{
        "question_id":None,"choice":None,
        "request_id":"french_content_version_01",
    }).status_code==200
    with runtime.store._tx() as db:
        row=db.execute(
            "SELECT content_id,display_language FROM events "
            "WHERE request_id='french_content_version_01'"
        ).fetchone()
    assert row["content_id"]==text["resource"]["content_id"]
    assert row["display_language"]=="fr"


def test_legacy_fictional_database_migrates_without_fabricating_event_locale(tmp_path):
    """An older SQLite data layout must still be readable by admin tools."""
    import sqlite3
    from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
    runtime,_,_=harness(tmp_path)
    fake_enroll(runtime,"F1")
    finish_pretest(runtime,"F1")
    db=sqlite3.connect(runtime.store.research)
    db.execute("ALTER TABLE participants DROP COLUMN study_language")
    db.execute("ALTER TABLE events DROP COLUMN display_language")
    db.commit()
    db.close()

    restored=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA))
    with restored._tx() as db:
        participant_columns={r["name"] for r in db.execute(
            "PRAGMA table_info(participants)"
        )}
        event_columns={r["name"] for r in db.execute("PRAGMA table_info(events)")}
        old_languages=db.execute(
            "SELECT DISTINCT display_language FROM events"
        ).fetchall()
    assert "study_language" in participant_columns
    assert "display_language" in event_columns
    assert old_languages and all(r["display_language"] is None for r in old_languages)
    ref,token=runtime.roster["F1"]
    assert restored.progress(ref,token)["study_language"]=="en"
