"""Supervisor's proposed NN: deterministic features and optional PyTorch trainer.

The instruction PDF contradicts itself: its feature list totals 20 numeric
features, but its architecture says Input(21). We implement the precisely
enumerated 20 features and BLOCK any release until the supervisor resolves
this schema discrepancy. No real Session 1 data or efficacy claim is supplied.

Never train on posttest, screening or recovery responses as if they were
independent practice observations. Extract only pre-question Q-matrix state:
using the after-question state would leak the label.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
import random
from typing import Iterable

from .supervisor_trace_engine import CONCEPT_IDS

FEATURE_VERSION = "SUPERVISOR_EXPLICIT_20_PENDING_21_RESOLUTION_V1"
FEATURE_NAMES = (
    *(f"mastery_{c}" for c in CONCEPT_IDS),
    "question_bloom_level_normalized",
    *(f"concept_onehot_{c}" for c in CONCEPT_IDS),
    "previous_response_time_normalized",
    "session_number_normalized",
    "current_target_bloom_normalized",
)
assert len(FEATURE_NAMES) == 20


@dataclass(frozen=True)
class TrainingExample:
    learner_id: str
    session: int
    features: tuple[float, ...]
    label: int
    event_id: int

    def __post_init__(self):
        if not self.learner_id.startswith("SYN_SUPERVISOR_"):
            # Genuine records require an approved separate data controller
            # pipeline, not this offline synthetic fixture extractor.
            raise ValueError("only fictional anonymized training examples supported")
        if self.session not in (1, 2, 3):
            raise ValueError("session 1,2,3 required")
        if len(self.features) != 20 or any(
            not math.isfinite(x) or not 0 <= x <= 1 for x in self.features
        ):
            raise ValueError("20 normalized finite predictor features required")
        if self.label not in (0, 1):
            raise ValueError("binary correctness label required")


def build_features(prior: dict, event: dict, *, last_response_ms: int=0) -> tuple[float, ...]:
    if event.get("phase") != "QUIZ" or event.get("action_type") != "QUESTION":
        raise ValueError("only normal adaptive quiz questions are eligible")
    c=event.get("concept_id")
    level=event.get("bloom_level")
    session=event.get("session_no")
    if (c not in CONCEPT_IDS or type(level) is not int
            or not 1 <= level <= 6 or type(session) is not int
            or session not in (1,2,3)):
        raise ValueError("invalid question feature metadata")
    if type(last_response_ms) is not int or last_response_ms < 0:
        raise ValueError("nonnegative previous response time required")
    mastery=prior.get("mastery")
    bloom=prior.get("bloom")
    if (not isinstance(mastery,dict) or set(mastery)!=set(CONCEPT_IDS)
            or not isinstance(bloom,dict) or set(bloom)!=set(CONCEPT_IDS)):
        raise ValueError("complete BEFORE-question state required")
    if any(type(bloom[k]) is not int or not 1<=bloom[k]<=6 for k in CONCEPT_IDS):
        raise ValueError("invalid historic Bloom level")
    vector=tuple(float(mastery[k]) for k in CONCEPT_IDS)+(
        level/6.0,
    )+tuple(float(k==c) for k in CONCEPT_IDS)+(
        min(last_response_ms,60000)/60000.0,
        session/3.0,
        bloom[c]/6.0,
    )
    if len(vector)!=20 or any(not math.isfinite(x)
                               or not 0<=x<=1 for x in vector):
        raise ValueError("unexpected 20-feature value range")
    return vector


def extract_fictional_training_examples(store, *, through_session: int=1):
    """Read already recorded synthetic events without touching contact vault."""
    from .supervisor_synthetic_store import SupervisorSyntheticStore
    if not isinstance(store,SupervisorSyntheticStore):
        raise TypeError("isolated supervisor store required")
    if through_session not in (1,2):
        raise ValueError("only supervised after-session-1/2 training allowed")
    results=[]
    with store._tx() as db:
        refs=[row["learner_id"] for row in db.execute(
            "SELECT learner_id FROM participants ORDER BY learner_id"
        )]
        for learner in refs:
            rows=db.execute(
                "SELECT e.*,h.state_json FROM events e "
                "JOIN state_history h ON h.event_id=e.event_id "
                "WHERE e.learner_id=? ORDER BY e.event_id",(learner,),
            ).fetchall()
            prior_state=None
            previous_response_ms=0
            for row in rows:
                ev=dict(row)
                if (ev["phase"]=="QUIZ" and ev["action_type"]=="QUESTION"
                        and ev["session_no"]<=through_session):
                    if not prior_state or not isinstance(prior_state.get("engine"),dict):
                        raise ValueError("missing pre-question adaptive state")
                    if type(ev["is_correct"]) is not int or ev["is_correct"] not in (0,1):
                        raise ValueError("scored normal answer required")
                    vector=build_features(
                        prior_state["engine"],ev,
                        last_response_ms=previous_response_ms,
                    )
                    results.append(TrainingExample(
                        learner_id=learner,session=ev["session_no"],
                        features=vector,label=ev["is_correct"],
                        event_id=ev["event_id"],
                    ))
                if ev["phase"]=="QUIZ" and ev["action_type"]=="QUESTION":
                    previous_response_ms=int(ev["response_time_ms"])
                prior_state=json.loads(row["state_json"])
    return tuple(results)


def split_by_learner(examples: Iterable[TrainingExample],
                     *, seed: int=20261111,validation_fraction: float=.25):
    """Prevent both visits of a learner leaking across train and validation."""
    items=tuple(examples)
    if not 0 < validation_fraction < .5:
        raise ValueError("validation_fraction must be between 0 and 0.5")
    learners=sorted(set(e.learner_id for e in items))
    if len(learners) < 4:
        raise ValueError("four or more fictional learners required for split")
    rng=random.Random(seed)
    rng.shuffle(learners)
    n_validation=max(1,round(len(learners)*validation_fraction))
    holdout=set(learners[:n_validation])
    train=tuple(e for e in items if e.learner_id not in holdout)
    valid=tuple(e for e in items if e.learner_id in holdout)
    if not train or not valid:
        raise ValueError("empty independent training/validation partition")
    if set(e.learner_id for e in train)&set(e.learner_id for e in valid):
        raise ValueError("learner leakage detected")
    return train,valid


def build_torch_model():
    """20→64 ReLU→Dropout(0.3)→32 ReLU→1 sigmoid, as explicitly enumerated."""
    from torch import nn
    return nn.Sequential(
        nn.Linear(20,64),nn.ReLU(),nn.Dropout(p=.3),
        nn.Linear(64,32),nn.ReLU(),nn.Linear(32,1),nn.Sigmoid(),
    )


def train_fictional_model(examples: Iterable[TrainingExample], *,
                          epochs: int=8,seed: int=71):
    """Purely synthetic smoke trainer, *not* scientific model validation.

    It intentionally cannot produce a release certificate or report AUC
    from a small laboratory smoke fixture as empirical study evidence.
    """
    if type(epochs) is not int or not 1<=epochs<=100:
        raise ValueError("epochs outside allowed range")
    train,valid=split_by_learner(examples,seed=seed)
    if len(train)<16 or len(valid)<4:
        raise ValueError("insufficient fictional interactions for train/validation")
    import torch
    from torch import nn
    torch.manual_seed(seed)
    model=build_torch_model()
    x=torch.tensor([e.features for e in train],dtype=torch.float32)
    y=torch.tensor([[e.label] for e in train],dtype=torch.float32)
    criterion=nn.BCELoss()
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    for _ in range(epochs):
        model.train();optimizer.zero_grad()
        pred=model(x)
        loss=criterion(pred,y)
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward();optimizer.step()
    model.eval()
    with torch.no_grad():
        xv=torch.tensor([e.features for e in valid],dtype=torch.float32)
        predictions=model(xv).flatten().tolist()
    return {
        "kind":"FICTIONAL_ONLY_NO_EMPIRICAL_EFFICACY",
        "feature_version":FEATURE_VERSION,
        "n_train":len(train),"n_validation":len(valid),
        "prediction_count":len(predictions),
        "predictions":tuple(predictions),
        "validation_labels":tuple(e.label for e in valid),
        "human_enrollment_authorized":False,
        "model_release_authorized":False,
    }
