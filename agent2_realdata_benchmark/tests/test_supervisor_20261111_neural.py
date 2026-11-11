"""NN feature semantics and split: no post-answer leakage or real data."""
from datetime import datetime,timezone
from pathlib import Path

import pytest

from src.prototype.supervisor_neural_training import (
    FEATURE_NAMES,FEATURE_VERSION,TrainingExample,
    build_features,extract_fictional_training_examples,
    split_by_learner,train_fictional_model,
)
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
NOW=datetime(2026,11,11,12,tzinfo=timezone.utc)


def test_20_features_reconstruct_pre_question_mastery_not_label():
    prior={
        "mastery":{f"C{i}":.1*i for i in range(1,9)},
        "bloom":{f"C{i}":i%6+1 for i in range(1,9)},
    }
    event={
        "phase":"QUIZ","action_type":"QUESTION","concept_id":"C2",
        "bloom_level":3,"session_no":1,
    }
    x=build_features(prior,event,last_response_ms=12000)
    assert len(FEATURE_NAMES)==len(x)==20
    assert x[0]==.1 and x[1]==.2
    assert x[8]==.5
    assert sum(x[9:17])==1
    assert x[10]==1
    assert x[17]==.2
    assert x[18]==pytest.approx(1/3)
    assert x[19]==.5
    assert "PENDING_21_RESOLUTION" in FEATURE_VERSION
    assert "answer_given" not in FEATURE_NAMES
    assert "is_correct" not in FEATURE_NAMES
    with pytest.raises(ValueError,match="only normal"):
        build_features(prior,event|{"phase":"POSTTEST"})
    with pytest.raises(ValueError,match="only normal"):
        build_features(prior,event|{"action_type":"DROP_2"})


def test_actual_sqlite_extract_uses_before_state_and_ignores_screen_pre_post(tmp_path):
    bank=SupervisorBank(DATA)
    store=SupervisorSyntheticStore(tmp_path,bank=bank)
    answers={q.question_id: next(k for k in "ABCD"
        if k!=q.correct_answer) for q in bank.forms["screening"]}
    record=store.register(
        contact_email="sample@example.test",econ_course=False,
        screening_answers=answers,consent_version="fixture",
        consent_given=True,age=23,program="Synthetic",at=NOW,
    )
    ref,token=record["fictional_learner_id"],record["fictional_private_token"]
    for i,q in enumerate(bank.forms["pretest"]):
        store.answer_assessment(ref,token,
            request_id=f"pretest_{i:03d}",item_id=q.question_id,
            choice=q.correct_answer,shown_at=NOW,answered_at=NOW,
        )
    first=store.next_item(ref,token)
    assert first["question_id"]=="QZ_C1_L1_01"
    store.answer_quiz(
        ref,token,request_id="supervisor_nn_q01",
        item_id=first["question_id"],
        choice=bank.get(first["question_id"],form="practice").correct_answer,
        shown_at=NOW,answered_at=NOW,
    )
    records=extract_fictional_training_examples(store)
    assert len(records)==1
    x=records[0]
    assert x.learner_id==ref and x.session==1
    assert x.label==1
    assert len(x.features)==20
    assert x.features[:8]==(.75,)*8  # before learning
    assert x.features[8]==pytest.approx(1/6)
    assert x.features[17]==0.0
    assert x.features[19]==pytest.approx(1/6)
    assert x.event_id>24
    assert not extract_fictional_training_examples(store,through_session=2)[1:]


def test_grouped_split_rejects_any_same_learner_train_validation_leakage():
    examples=[
        TrainingExample(
            learner_id=f"SYN_SUPERVISOR_P{i:03d}",session=1,
            features=(.5,)*20,label=(j+i)%2,
            event_id=i*100+j,
        ) for i in range(1,9) for j in range(6)
    ]
    train,val=split_by_learner(examples,seed=73)
    assert len(train)+len(val)==48
    assert not {x.learner_id for x in train}&{x.learner_id for x in val}
    assert split_by_learner(examples,seed=73)==(train,val)
    with pytest.raises(ValueError,match="four or more"):
        split_by_learner(examples[:6])


def test_torch_architecture_and_fake_training_when_installed():
    torch=pytest.importorskip("torch")
    examples=[
        TrainingExample(
            learner_id=f"SYN_SUPERVISOR_P{i:03d}",session=1,
            features=tuple((i+j+k)%10/10 for k in range(20)),
            label=(i+j)%2,event_id=i*100+j,
        ) for i in range(1,9) for j in range(6)
    ]
    from src.prototype.supervisor_neural_training import build_torch_model
    model=build_torch_model()
    assert model[0].in_features==20
    assert model[0].out_features==64
    assert model[3].in_features==64
    assert model[3].out_features==32
    assert model[5].out_features==1
    assert model[2].p==.3
    result=train_fictional_model(examples,epochs=2,seed=8)
    assert result["prediction_count"]==len(result["validation_labels"])
    assert not result["model_release_authorized"]
    assert not result["human_enrollment_authorized"]
