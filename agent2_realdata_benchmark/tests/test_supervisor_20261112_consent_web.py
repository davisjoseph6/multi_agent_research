"""HTTP acceptance for the staged, NO-NETWORK fictional GDPR browser."""
from datetime import datetime, timezone
from pathlib import Path
import re

import pytest

from scripts.supervisor_fictional_browser import new_supervisor_fictional_runtime
from src.prototype.supervisor_consent_texts import (
    CONSENT_VERSION, EN_REQUIRED, FR_REQUIRED, EN_OPTIONAL, FR_OPTIONAL,
    INELIGIBLE, REGISTERED, DELETE_CONFIRMATION, KEEP_CONFIRMATION,
)
from src.prototype.supervisor_fictional_web import make_supervisor_fictional_app

PORT=8783
BASE=f"http://127.0.0.1:{PORT}"


@pytest.fixture
def h(tmp_path):
    runtime=new_supervisor_fictional_runtime(tmp_path)
    app=make_supervisor_fictional_app(runtime,port=PORT)
    app.config["TESTING"]=True
    client=app.test_client()
    html=client.get("/",base_url=BASE).get_data(as_text=True)
    nonce=re.search(r'data-preview-nonce="([^"]+)"',html).group(1)
    return runtime,client,nonce


def post(h,route,data=None,fixture="F1"):
    _,client,nonce=h
    return client.post(
        "/supervisor/api/"+route,
        json={"fixture":fixture,**(data or {})},
        headers={"X-Preview-Nonce":nonce,"Origin":BASE},
        base_url=BASE,
    )


def ok(h,route,data=None,fixture="F1"):
    response=post(h,route,data,fixture)
    assert response.status_code==200,(route,response.status_code,response.json)
    return response.json


def answer_map(runtime,correct):
    return {
        q.question_id:(
            q.correct_answer if i<correct else
            next(c for c in "ABCD" if c!=q.correct_answer)
        ) for i,q in enumerate(runtime.store.bank.forms["screening"])
    }


def accepted(h,fixture="F1",lang="en",optional=False,score=4):
    ok(h,"consent/start",{
        "checks":[True]*6,"optional":optional,"language":lang,
    },fixture)
    assert ok(h,"status",fixture=fixture)["consent_stage"]=="screening"
    result=ok(h,"consent/screen",{
        "answers":answer_map(h[0],score),
    },fixture)
    return result


def registered(h,fixture="F1",lang="en",optional=False,email="a@example.test"):
    assert accepted(h,fixture,lang,optional)["eligible"]
    return ok(h,"consent/register",{
        "email":email,"age":23,"program":"Synthetic classroom demonstration",
    },fixture)


def test_information_sheets_and_required_copy_present_exactly(h):
    runtime,client,nonce=h
    for lang,expected in (("en",EN_REQUIRED),("fr",FR_REQUIRED)):
        r=client.get(f"/content/consent/{lang}/info",base_url=BASE)
        assert r.status_code==200
        assert "v1.0" in r.get_data(as_text=True)
        assert ("Who runs the study?" if lang=="en" else "Qui mène l’étude") in r.get_data(as_text=True)
        copy=ok(h,"consent/copy",{"language":lang})
        assert copy["version"]==CONSENT_VERSION
        assert copy["required"]==list(expected)
        assert copy["optional"]==(EN_OPTIONAL if lang=="en" else FR_OPTIONAL)
    assert client.get("/supervisor/consent",base_url=BASE).status_code==302
    assert client.get("/supervisor/stop",base_url=BASE).status_code==302
    home=client.get("/",base_url=BASE).get_data(as_text=True)
    for id in ("start-consent","consent-required","consent-optional",
               "withdraw-keep","withdraw-delete","footer-stop"):
        assert f'id="{id}"' in home
    assert 'id="start-consent" disabled' in home


def test_five_checked_rejected_by_server_and_no_stored_intake(h):
    runtime,_,_=h
    r=post(h,"consent/start",{
        "checks":[True]*5+[False],"optional":True,"language":"en",
    })
    assert r.status_code==409 and not runtime.consent.drafts
    with runtime.store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0


def test_optional_does_not_control_six_required_gate(h):
    assert accepted(h,optional=False)["eligible"]
    outcome=ok(h,"consent/register",{
        "email":"case@example.test","age":23,
        "program":"Synthetic classroom demonstration",
    })
    assert outcome["registered"] and outcome["message"]==REGISTERED
    with h[0].store._tx() as db:
        assert db.execute(
            "SELECT open_data_consent FROM participants"
        ).fetchone()["open_data_consent"]==0


def test_econ_link_never_writes_any_registration_data(h):
    ok(h,"consent/start",{
        "checks":[True]*6,"optional":False,"language":"en",
    })
    outcome=ok(h,"consent/economics")
    assert outcome["message"]==INELIGIBLE
    assert ok(h,"status")["consent_stage"]=="excluded"
    with h[0].store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM screening_log").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0


def test_six_screen_correct_writes_one_anonymous_row_only(h):
    ok(h,"consent/start",{
        "checks":[True]*6,"optional":False,"language":"en",
    })
    denied=ok(h,"consent/screen",{"answers":answer_map(h[0],6)})
    assert not denied["eligible"] and denied["message"]==INELIGIBLE
    with h[0].store._tx() as db:
        row=db.execute(
            "SELECT timestamp,score,eligible FROM screening_log",
        ).fetchone()
        assert row["score"]==6 and row["eligible"]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0


def test_valid_fr_registration_hash_only_and_no_token_in_http(h):
    result=registered(h,lang="fr",optional=True)
    assert result["registered"]
    assert "token" not in str(result).lower()
    assert not result["real_email_sent"]
    assert ok(h,"status")["consent_lang"]=="fr"
    assert h[0].consent.private_mail_preview[0]["recipient"]=="a@example.test"
    with h[0].store._tx() as db:
        p=db.execute(
            "SELECT consent_version,consent_lang,open_data_consent FROM participants"
        ).fetchone()
        assert (p["consent_version"],p["consent_lang"],
                p["open_data_consent"])==("v1.0","fr",1)


def test_duplicate_email_cannot_allocate_next_arm(h):
    registered(h)
    accepted(h,fixture="F2")
    r=post(h,"consent/register",{
        "email":"A@example.test","age":23,
        "program":"Synthetic classroom demonstration",
    },fixture="F2")
    assert r.status_code==409 and "already registered" in r.json["error"]
    with h[0].store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1


def test_stop_keep_revokes_link_preserves_research(h):
    registered(h)
    ref,token=h[0].roster["F1"]
    denied=post(h,"consent/withdraw",{"delete":False,"confirmed":False})
    assert denied.status_code==409
    done=ok(h,"consent/withdraw",{"delete":False,"confirmed":True})
    assert done["message"]==KEEP_CONFIRMATION and not done["real_email_sent"]
    assert "F1" not in h[0].roster
    with h[0].store._tx() as db:
        assert db.execute("SELECT status FROM participants").fetchone()["status"]=="withdrawn"
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==8


def test_stop_delete_erases_all_and_logs_once(h):
    registered(h)
    done=ok(h,"consent/withdraw",{"delete":True,"confirmed":True})
    assert done["message"]==DELETE_CONFIRMATION
    with h[0].store._tx() as db:
        for table in ("participants","sessions","learner_state","events",
                      "state_history","surveys"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
        logs=db.execute("SELECT learner_id,channel FROM deletion_log").fetchall()
        assert len(logs)==1 and logs[0]["channel"]=="website"


def test_legacy_one_checkbox_direct_registration_blocked_outside_tests(h):
    runtime,client,nonce=h
    # The old API remains for existing synthetic unit tests, not the running
    # browser. The deployed-facing fixture path is gated by the staged flow.
    client.application.config["TESTING"]=False
    r=post(h,"register",{
        "consent":True,"econ_course":False,"screening_answers":{},
    })
    assert r.status_code==409
    r=post(h,"screening")
    assert r.status_code==409


def test_info_pdf_generator_emits_both_valid_documents(tmp_path):
    from scripts.supervisor_consent_pdf import build_pdfs
    files=build_pdfs(tmp_path)
    assert len(files)==2
    for item in files:
        assert item.stat().st_size>1500
        assert item.read_bytes().startswith(b"%PDF-")
