"""Aivancity-only incentive: server-derived exact verified invitation domain.

No real email is delivered; this is an isolated offline unit test. Existing
v1.0 institutional consent is preserved verbatim and the new nonreward
v1.1 wording still requires documented institutional approval.
"""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_consent_texts import (
    CONSENT_VERSION, NONREWARD_CONSENT_VERSION, EN_REQUIRED, FR_REQUIRED,
    required_for_recipient,is_aivancity_recipient,
)
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_vps_web import make_supervisor_vps_app

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
NOW=lambda:datetime.now(timezone.utc)
BASE="http://127.0.0.1:8788"


@pytest.mark.parametrize("email,eligible",[
    ("davis.joseph@aivancity.education",True),
    ("mary.jane@aivancity.education",True),
    ("STUDENT@AIVANCITY.EDUCATION",True),
    ("external@university.edu",False),
    ("researcher@example.example",False),
    ("other@aivancity.education.evil.com",False),
    ("staff@sub.aivancity.education",False),
    ("staff@aivancity.educationx",False),
])
def test_exact_email_domain_controls_ai_points(email,eligible):
    assert is_aivancity_recipient(email) is eligible
    for language in ("en","fr"):
        required,optional,version,qualified=required_for_recipient(language,email)
        assert qualified is eligible
        assert len(required)==(6 if eligible else 5)
        assert version==(CONSENT_VERSION if eligible else NONREWARD_CONSENT_VERSION)
        assert bool(any("150 AI points" in s for s in required)) is eligible
        assert bool(optional)


def harness(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA),operational=True)
    intake=OperationalIntake(store,programs=("Research test program",))
    app=make_supervisor_vps_app(
        intake,hostname="demo.selfhealing-edu.fr",proxy_mode=False,
        release_mode="staging",
    )
    client=app.test_client()
    def post(path,data=None):
        return client.post("/study/api/"+path,json={} if data is None else data,
                           base_url=BASE,headers={
                               "Origin":BASE,"Content-Type":"application/json",
                               "X-Study-Request":"1",
                           })
    return store,intake,client,post


@pytest.mark.parametrize("email,expected_checks,expected_version",[
    ("davis.joseph@aivancity.education",6,CONSENT_VERSION),
    ("external@outside.org",5,NONREWARD_CONSENT_VERSION),
    ("other@aivancity.education.evil.org",5,NONREWARD_CONSENT_VERSION),
])
def test_privately_scoped_consent_and_registration(tmp_path,email,expected_checks,expected_version):
    store,intake,client,post=harness(tmp_path)
    token=intake.issue(email,at=NOW(),allow_example=False)
    assert post("consent-copy",{"language":"en"}).status_code==409
    assert post("exchange",{"token":token}).status_code==200
    info=post("consent-copy",{"language":"en"}).json
    assert len(info["required"])==expected_checks
    assert info["version"]==expected_version
    assert info["ai_points_eligible"] is (expected_checks==6)
    assert email not in str(info)
    page=client.get("/study/info/en",base_url=BASE)
    assert page.status_code==200
    html=page.get_data(as_text=True)
    if expected_checks==5:
        assert "v1.1" in html and "No AI points" in html
        assert "150 AI points" not in html
    else:
        assert "v1.0" in html and "150 AI points" in html

    too_short=post("consent",{
        "checks":[True]*(expected_checks-1), "optional":False,"language":"en",
    })
    assert too_short.status_code==409
    assert post("consent",{
        "checks":[True]*expected_checks,"optional":False,"language":"en",
    }).status_code==200

    questions=store.bank.forms["screening"]
    answers={
        q.question_id: q.correct_answer if i<4 else next(
            c for c in "ABCD" if c!=q.correct_answer
        ) for i,q in enumerate(questions)
    }
    assert post("screen",{"answers":answers}).json["eligible"]
    registered=post("register",{"age":24,"program":"Research test program"})
    assert registered.status_code==200,registered.json
    with store._tx() as db:
        row=db.execute("SELECT consent_version FROM participants").fetchone()
    assert row["consent_version"]==expected_version


def test_legacy_synthetic_consent_is_not_changed():
    assert len(EN_REQUIRED)==len(FR_REQUIRED)==6
    assert EN_REQUIRED[4].startswith("I understand that the 150 AI points")
    assert CONSENT_VERSION=="v1.0"
