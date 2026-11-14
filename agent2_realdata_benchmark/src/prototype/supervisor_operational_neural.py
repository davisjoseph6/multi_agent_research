"""Independent offline neural evaluation against BKT, on approved research data.

This module NEVER attaches the PII/contact DB or calls the participant API.
It extracts exactly the canonical supervisor's 20 named pre-question
features from versioned, append-only research events, enforcing
participant-wise holdout. The historic PDF also says Input(21) without
naming a 21st variable; this code refuses to invent an extra predictor.
Actual data access, neural training and model release require a PI-signed
feature contract and institutional data-controller authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import sqlite3

from .supervisor_neural_training import FEATURE_NAMES, build_features, build_torch_model

P_CORRECT_SLIP = 0.10
P_CORRECT_GUESS = 0.25


@dataclass(frozen=True)
class OperationalExample:
    learner_id: str
    session: int
    event_id: int
    features: tuple[float, ...]
    label: int
    bkt_pred: float

    def __post_init__(self):
        if not (self.learner_id.startswith("STUDY_P") and
                self.learner_id[7:].isdigit()):
            raise ValueError("operational pseudonymous ID required")
        if self.session not in (1,2,3) or len(self.features) != len(FEATURE_NAMES):
            raise ValueError("invalid study session or feature length")
        if (self.label not in (0,1) or not 0<=self.bkt_pred<=1
                or any(not math.isfinite(x) or not 0<=x<=1 for x in self.features)):
            raise ValueError("invalid normalized training example")


def open_research_readonly(path: str | Path):
    path = Path(path)
    if (not path.is_file() or path.is_symlink()
            or path.name != "supervisor_operational_study.sqlite3"):
        raise ValueError("existing non-symlink operational research database required")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def extract_examples(path: str | Path, *, through_session: int = 1):
    """Read chronological research-only events; no after-answer data leakage."""
    if type(through_session) is not int or through_session not in (1,2):
        raise ValueError("PI-approved session 1 or 2 extraction required")
    result = []
    db = open_research_readonly(path)
    try:
        learners = db.execute(
            "SELECT learner_id FROM participants ORDER BY learner_id"
        ).fetchall()
        for person in learners:
            learner = person["learner_id"]
            events = db.execute(
                "SELECT e.*,h.state_json FROM events e "
                "JOIN state_history h USING(event_id) "
                "WHERE e.learner_id=? ORDER BY e.event_id", (learner,),
            ).fetchall()
            previous = None
            last_normal_response_ms = 0
            for row in events:
                event = dict(row)
                if (event["phase"] == "QUIZ" and
                    event["action_type"] == "QUESTION" and
                    event["session_no"] <= through_session):
                    if not previous or not isinstance(previous.get("engine"),dict):
                        raise ValueError("missing BEFORE-question BKT state")
                    if event["is_correct"] not in (0,1):
                        raise ValueError("missing scored correctness")
                    features = build_features(
                        previous["engine"], event,
                        last_response_ms=last_normal_response_ms,
                    )
                    concept = event["concept_id"]
                    m = previous["engine"]["mastery"][concept]
                    if not isinstance(m,(float,int)) or not 0<=m<=1:
                        raise ValueError("invalid previous BKT mastery")
                    bkt = m*(1-P_CORRECT_SLIP)+(1-m)*P_CORRECT_GUESS
                    result.append(OperationalExample(
                        learner_id=learner,session=event["session_no"],
                        event_id=event["event_id"],features=features,
                        label=int(event["is_correct"]),bkt_pred=float(bkt),
                    ))
                if (event["phase"]=="QUIZ" and
                    event["action_type"]=="QUESTION"):
                    last_normal_response_ms=int(event["response_time_ms"])
                previous=json.loads(event["state_json"])
    finally:
        db.close()
    return tuple(result)


def split_by_student(examples, *, fraction=.25, seed=20261111):
    examples = tuple(examples)
    ids = sorted({e.learner_id for e in examples})
    if len(ids)<8:
        raise ValueError("at least 8 distinct consenting research participants needed")
    if not .1 <= fraction <= .4:
        raise ValueError("validation fraction 0.1..0.4 required")
    rng = random.Random(seed)
    rng.shuffle(ids)
    n = max(2, round(fraction*len(ids)))
    held = set(ids[:n])
    training = tuple(e for e in examples if e.learner_id not in held)
    validation = tuple(e for e in examples if e.learner_id in held)
    if not training or not validation:
        raise ValueError("independent holdout must not be empty")
    if {e.learner_id for e in training}&{e.learner_id for e in validation}:
        raise ValueError("subject-level data leakage")
    return training,validation


def auc(y, probabilities):
    """Tie-safe rank AUC; raises for a validation set with only one class."""
    vals = tuple(zip(y, probabilities))
    if not vals or any(label not in (0,1) or not math.isfinite(p)
                       or not 0<=p<=1 for label,p in vals):
        raise ValueError("valid binary labels and probabilities required")
    positives = sum(label for label,_ in vals)
    negatives = len(vals)-positives
    if not positives or not negatives:
        raise ValueError("both classes required for interpretable AUC")
    vals = sorted(vals,key=lambda a:a[1])
    rank=1
    positive_ranks=0.0
    i=0
    while i<len(vals):
        j=i+1
        while j<len(vals) and vals[j][1]==vals[i][1]:
            j+=1
        mid_rank=(rank+rank+(j-i)-1)/2
        positive_ranks+=sum(label for label,_ in vals[i:j])*mid_rank
        rank+=j-i
        i=j
    return (positive_ranks-positives*(positives+1)/2)/(positives*negatives)


def score(y, probabilities):
    labels=tuple(y)
    probs=tuple(probabilities)
    if len(labels)!=len(probs) or not labels:
        raise ValueError("matched nonempty labels and predictions required")
    if any(label not in (0,1) or not math.isfinite(p) or not 0<=p<=1
           for label,p in zip(labels,probs)):
        raise ValueError("invalid labels or predictions")
    return {
        "auc":round(auc(labels,probs),6),
        "brier":round(sum((p-y)**2 for y,p in zip(labels,probs))/len(labels),6),
        "n":len(labels),
        "positive_rate":round(sum(labels)/len(labels),6),
    }


def train_and_compare(examples, *, epochs=8, seed=73, dkt_predictions=None):
    """Train independent heldout NN, BKT baseline, optionally aligned DKT.

    PyTorch is needed in the separately authorized research environment, not
    the public VPS. No participant-facing model deployment occurs here.
    """
    training,validation=split_by_student(examples,seed=seed)
    if type(epochs) is not int or not 1<=epochs<=100:
        raise ValueError("epochs must be 1..100")
    import torch
    from torch import nn

    torch.manual_seed(seed)
    model=build_torch_model()
    train_x=torch.tensor([e.features for e in training],dtype=torch.float32)
    train_y=torch.tensor([[e.label] for e in training],dtype=torch.float32)
    opt=torch.optim.Adam(model.parameters(),lr=.001)
    criterion=nn.BCELoss()
    for _ in range(epochs):
        model.train();opt.zero_grad()
        loss=criterion(model(train_x),train_y)
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward();opt.step()
    model.eval()
    with torch.no_grad():
        pred=model(torch.tensor(
            [e.features for e in validation],dtype=torch.float32,
        )).flatten().tolist()
    labels=[e.label for e in validation]
    metrics={
        "neural":score(labels,pred),
        "bkt":score(labels,[e.bkt_pred for e in validation]),
    }
    if dkt_predictions is not None:
        if set(dkt_predictions)!={e.event_id for e in validation}:
            raise ValueError("DKT predictions must match exact heldout event IDs")
        metrics["dkt"]=score(labels,[
            dkt_predictions[e.event_id] for e in validation
        ])
    return {
        "feature_names":list(FEATURE_NAMES),
        "feature_count":20,
        "n_train_students":len({e.learner_id for e in training}),
        "n_validation_students":len({e.learner_id for e in validation}),
        "n_train_events":len(training),
        "n_validation_events":len(validation),
        "metrics":metrics,
        "training_through_session":max(e.session for e in training),
        "grouped_holdout":True,
        "live_participant_algorithm_unchanged":True,
        "model_release_approved":False,
    }
