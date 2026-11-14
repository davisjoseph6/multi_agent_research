"""Operational research-only supervised model pipeline, without real data."""
from __future__ import annotations
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import subprocess

import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_neural_training import FEATURE_NAMES
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_operational_neural import (
    OperationalExample, extract_examples, split_by_student, score, auc,
    train_and_compare,
)
from scripts.supervisor_operational_neural_cli import (
    verified_feature_contract,save_private,load_dkt,
)

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
NOW=lambda:datetime.now(timezone.utc)


def test_auc_brier_and_exact_prediction_contract():
    assert auc([0,1],[0.1,0.9])==1.0
    assert auc([0,1],[0.9,0.1])==0.0
    assert auc([0,1],[.5,.5])==.5
    assert score([0,1],[0,1])=={
        "auc":1.0,"brier":0.0,"n":2,"positive_rate":.5}
    with pytest.raises(ValueError,match="both classes"):
        score([1,1],[.3,.5])
    with pytest.raises(ValueError,match="invalid"):
        score([0,1],[.5,1.3])


def test_grouped_student_holdout_has_no_repeated_subject(tmp_path):
    examples=tuple(
        OperationalExample(
            learner_id=f"STUDY_P{i:03d}",session=(j%3+1),
            event_id=i*10+j,features=(.5,)*20,label=(i+j)%2,bkt_pred=.6
        ) for i in range(1,13) for j in range(4)
    )
    train,val=split_by_student(examples)
    assert train and val
    assert not ({e.learner_id for e in train}&{e.learner_id for e in val})
    assert split_by_student(examples)==(train,val)
    with pytest.raises(ValueError,match="8 distinct"):
        split_by_student(examples[:4])


def test_extract_operational_sqlite_respects_before_question_mastery(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA),
                                   operational=True)
    intake=OperationalIntake(store,programs=("Research test",))
    token=intake.issue("researcher@example.example",at=NOW(),allow_example=True)
    intake.consent(token,checks=[True]*5,optional=False,language="en",at=NOW())
    screen={q.question_id:(q.correct_answer if i<4 else next(
        c for c in "ABCD" if c!=q.correct_answer
    )) for i,q in enumerate(store.bank.forms["screening"])}
    assert intake.screening(token,answers=screen,at=NOW())["eligible"]
    assert intake.register(token,age=24,program="Research test",at=NOW())["registered"]
    ref=intake.learner(token,at=NOW())
    for i,q in enumerate(store.bank.forms["pretest"]):
        store.answer_assessment(
            ref,token,request_id=f"real_nn_pre_{i:02d}",
            item_id=q.question_id,choice=q.correct_answer,
            shown_at=NOW(),answered_at=NOW(),
        )
    item=store.next_item(ref,token)
    answer=store.bank.get(item["question_id"],form="practice").correct_answer
    store.answer_quiz(
        ref,token,request_id="real_nn_quiz_01",item_id=item["question_id"],
        choice=answer,shown_at=NOW(),answered_at=NOW(),
    )
    before=store.research.read_bytes()
    data=extract_examples(store.research)
    assert len(data)==1
    assert data[0].learner_id==ref
    assert data[0].features[:8]==(.75,)*8
    assert data[0].bkt_pred==pytest.approx(.75*.9+.25*.25)
    assert data[0].label==1
    assert store.research.read_bytes()==before
    assert len(FEATURE_NAMES)==20
    with pytest.raises(ValueError,match="operational research"):
        extract_examples(store.contacts)


def test_approval_signature_is_required_for_neural_pipeline(tmp_path):
    openssl=subprocess.run(["openssl","version"],capture_output=True)
    if openssl.returncode:
        pytest.skip("OpenSSL unavailable")
    contract=tmp_path/"approved_features.json"
    key=tmp_path/"pi.key"
    public=tmp_path/"pi.pub"
    signature=tmp_path/"pi.sig"
    data={
        "schema":"SUPERVISOR_NN_FEATURE_CONTRACT_V1",
        "decision":"approved","feature_count":20,
        "feature_names":list(FEATURE_NAMES),
        "reviewer":"Synthetic Unit-Test Authority",
        "approved_at":"2026-11-12T19:00:00+00:00",
        "institutional_data_use_reference":"TEST-NOT-REAL-APPROVAL",
    }
    contract.write_text(json.dumps(data),encoding="utf-8")
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-pkeyopt",
                    "rsa_keygen_bits:2048","-out",str(key)],
                   check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(key),"-pubout",
                    "-out",str(public)],check=True,capture_output=True)
    subprocess.run(["openssl","dgst","-sha256","-sign",str(key),
                    "-out",str(signature),str(contract)],check=True,capture_output=True)
    assert verified_feature_contract(contract,signature,public)["feature_count"]==20
    data["feature_count"]=21
    contract.write_text(json.dumps(data),encoding="utf-8")
    with pytest.raises(ValueError,match="signature"):
        verified_feature_contract(contract,signature,public)


def test_dkt_alignment_and_private_export(tmp_path):
    file=tmp_path/"dkt.csv"
    file.write_text("event_id,probability_correct\n11,0.7\n12,0.4\n",
                    encoding="utf-8")
    assert load_dkt(file)=={11:.7,12:.4}
    file.write_text("event_id,probability_correct\n11,0.7\n11,0.4\n",
                    encoding="utf-8")
    with pytest.raises(ValueError,match="duplicate"):
        load_dkt(file)
    output=tmp_path/"metrics.json"
    save_private(output,{"auc":1.0,"includes_names":False})
    assert json.loads(output.read_text())["auc"]==1.0
    with pytest.raises(ValueError,match="new absolute"):
        save_private(output,{"auc":0.0})
    assert output.stat().st_mode & 0o077==0
