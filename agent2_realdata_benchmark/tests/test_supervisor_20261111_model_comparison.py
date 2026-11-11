"""Paired ROC-AUC contract, synthetic heldout only."""
from dataclasses import replace

import pytest

from src.prototype.supervisor_model_comparison import (
    Prediction,compare_models,MODEL_NAMES,
)


def fixture():
    rows={}
    for model in MODEL_NAMES:
        candidates=[]
        for learner in range(1,4):
            for j in range(1,7):
                label=(learner+j)%2
                p_good=.9 if label else .1
                p=(
                    p_good if model=="NN" else
                    (.7 if label else .3) if model=="BKT" else
                    .5
                )
                candidates.append(Prediction(
                    learner_id=f"SYN_SUPERVISOR_P{learner:03d}",
                    event_id=str(learner*100+j),
                    phase="QUIZ",action_type="QUESTION",
                    label=label,probability=p,
                ))
        rows[model]=tuple(candidates)
    return rows


def test_model_comparison_is_paired_and_all_three_present():
    rows=fixture()
    holdout=frozenset(f"SYN_SUPERVISOR_P{i:03d}" for i in range(1,4))
    out=compare_models(rows,heldout_learners=holdout)
    assert set(out["models"])==set(MODEL_NAMES)
    assert out["models"]["NN"]["roc_auc"]==1.0
    assert out["models"]["BKT"]["roc_auc"]==1.0
    assert out["models"]["DKT"]["roc_auc"]==.5
    assert out["models"]["NN"]["brier"]<out["models"]["BKT"]["brier"]
    assert not out["human_enrollment_authorized"]
    assert not out["scientific_effectiveness_established"]


def test_no_label_or_cohort_mismatches():
    rows=fixture()
    holdout=frozenset(f"SYN_SUPERVISOR_P{i:03d}" for i in range(1,4))
    with pytest.raises(ValueError,match="all required"):
        compare_models({"NN":rows["NN"],"BKT":rows["BKT"]},
                       heldout_learners=holdout)
    wrong=tuple(replace(rows["DKT"][0],label=1-rows["DKT"][0].label)
                if i==0 else q for i,q in enumerate(rows["DKT"]))
    with pytest.raises(ValueError,match="label mismatch"):
        compare_models(rows|{"DKT":wrong},heldout_learners=holdout)
    with pytest.raises(ValueError,match="holdout"):
        compare_models(rows,heldout_learners=frozenset(["SYN_SUPERVISOR_P001"]))
    with pytest.raises(ValueError,match="different evaluation"):
        compare_models(rows|{"DKT":rows["DKT"][:-1]},
                       heldout_learners=holdout)


def test_reject_nonquiz_and_posttest_data():
    with pytest.raises(ValueError,match="only normal adaptive"):
        Prediction("SYN_SUPERVISOR_P001","e1","POSTTEST","QUESTION",1,.6)
    with pytest.raises(ValueError,match="only normal adaptive"):
        Prediction("SYN_SUPERVISOR_P001","e1","QUIZ","DROP_2",1,.6)
    with pytest.raises(ValueError,match="probability"):
        Prediction("SYN_SUPERVISOR_P001","e1","QUIZ","QUESTION",1,float("nan"))


def test_single_class_holdout_auc_is_not_fabricated():
    rows=fixture()
    converted={
        model:tuple(replace(r,label=1) for r in rs)
        for model,rs in rows.items()
    }
    holdout=frozenset(f"SYN_SUPERVISOR_P{i:03d}" for i in range(1,4))
    with pytest.raises(ValueError,match="undefined"):
        compare_models(converted,heldout_learners=holdout)
