"""Paired, deidentified NN/BKT/DKT comparison on matched held-out outcomes.

This is an analysis contract only: no Session-1/Session-2 real participant
data or evaluated neural/DKT predictions have been provided. It refuses
unaligned labels, duplicate events, assessment leakage, singleton-class
samples or invalid probability values. It cannot certify the PDF AUC goal.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path

MODEL_NAMES=("NN","BKT","DKT")


@dataclass(frozen=True)
class Prediction:
    learner_id: str
    event_id: str
    phase: str
    action_type: str
    label: int
    probability: float

    def __post_init__(self):
        if not self.learner_id.startswith("SYN_SUPERVISOR_"):
            raise ValueError("only synthetic comparison identifiers accepted")
        if not self.event_id or self.phase!="QUIZ" or self.action_type!="QUESTION":
            raise ValueError("only normal adaptive quiz observations permitted")
        if type(self.label) is not int or self.label not in (0,1):
            raise ValueError("binary label required")
        if (not isinstance(self.probability,(int,float))
                or not math.isfinite(self.probability)
                or not 0<=self.probability<=1):
            raise ValueError("finite probability within [0,1] required")

    @property
    def key(self):
        return (self.learner_id,self.event_id)


def read_prediction_csv(path: str | Path):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        expected={
            "learner_id","event_id","phase","action_type",
            "observed_correct","predicted_probability",
        }
        if not expected.issubset(reader.fieldnames or ()):
            raise ValueError("prediction file missing mandatory comparison fields")
        result=[]
        for row in reader:
            if row["observed_correct"] not in ("0","1"):
                raise ValueError("nonbinary observed outcome")
            result.append(Prediction(
                learner_id=row["learner_id"],
                event_id=row["event_id"],phase=row["phase"],
                action_type=row["action_type"],
                label=int(row["observed_correct"]),
                probability=float(row["predicted_probability"]),
            ))
    if not result or len({x.key for x in result})!=len(result):
        raise ValueError("missing rows or duplicate learner/event pairs")
    return tuple(result)


def _auc(labels,probs):
    """ROC AUC via Mann–Whitney ranking with exact tie-averaging."""
    positives=sum(labels)
    negatives=len(labels)-positives
    if positives==0 or negatives==0:
        raise ValueError("ROC AUC undefined for a single-class holdout")
    ordered=sorted(zip(probs,labels),key=lambda x:x[0])
    positive_rank_sum=0.0
    i=0
    while i<len(ordered):
        end=i+1
        while end<len(ordered) and ordered[end][0]==ordered[i][0]:
            end+=1
        rank=(i+1+end)/2.0
        positive_rank_sum+=rank*sum(y for _,y in ordered[i:end])
        i=end
    return (positive_rank_sum-positives*(positives+1)/2)/(positives*negatives)


def compare_models(aligned: dict[str,tuple[Prediction,...]],
                   *, heldout_learners: frozenset[str]):
    if set(aligned)!=set(MODEL_NAMES):
        raise ValueError("NN/BKT/DKT predictions all required")
    if not heldout_learners or any(
            not learner.startswith("SYN_SUPERVISOR_")
            for learner in heldout_learners):
        raise ValueError("independent fictional holdout list required")
    tables={}
    for model in MODEL_NAMES:
        rows=aligned[model]
        if not rows:
            raise ValueError("empty model predictions")
        table={r.key:r for r in rows}
        if len(table)!=len(rows):
            raise ValueError("duplicate prediction event")
        if set(k[0] for k in table)!=heldout_learners:
            raise ValueError("predictions do not match sealed holdout cohort")
        tables[model]=table
    keys=set(tables["NN"])
    if any(set(tables[model])!=keys for model in MODEL_NAMES):
        raise ValueError("different evaluation observations across models")
    ordered=sorted(keys)
    targets=[tables["NN"][key].label for key in ordered]
    if any(tables[model][key].label!=targets[i]
           for model in MODEL_NAMES for i,key in enumerate(ordered)):
        raise ValueError("model label mismatch")
    comparison={}
    for model in MODEL_NAMES:
        probabilities=[tables[model][key].probability for key in ordered]
        comparison[model]={
            "n":len(ordered),
            "roc_auc":round(_auc(targets,probabilities),6),
            "brier":round(sum((p-y)**2 for p,y in zip(probabilities,targets))
                          /len(ordered),6),
            "auc_over_0_75":_auc(targets,probabilities)>.75,
        }
    return {
        "kind":"SYNTHETIC_MATCHED_HOLDOUT_COMPARISON_ONLY",
        "human_enrollment_authorized":False,
        "scientific_effectiveness_established":False,
        "n_learners":len(heldout_learners),
        "n_observations":len(keys),
        "models":comparison,
    }
