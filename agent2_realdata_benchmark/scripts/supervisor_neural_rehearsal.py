"""Offline-only supervisor neural architecture and synthetic training CLI.

The 20-vs-21 input discrepancy in Experimentation.pdf remains unresolved;
outputs cannot justify human-study deployment or claim any real AUC.
Real Session1 outcomes must only enter a separate institutionally authorized
pipeline, NOT this fictional tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_fictional_backup import _check_only_fake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_neural_training import (
    FEATURE_NAMES,FEATURE_VERSION,TrainingExample,
    extract_fictional_training_examples,train_fictional_model,
)

ROOT=Path(__file__).resolve().parents[1]


def self_test_examples():
    return tuple(
        TrainingExample(
            learner_id=f"SYN_SUPERVISOR_P{i:03d}",session=1,
            features=tuple((i+2*j+k)%10/10 for k in range(20)),
            label=(i+j)%2,event_id=i*1000+j,
        )
        for i in range(1,9) for j in range(12)
    )


def main():
    p=argparse.ArgumentParser(
        description="Fictional supervisor 20-feature NN smoke rehearsal")
    p.add_argument("--feature-contract",action="store_true")
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--state-dir",type=Path)
    p.add_argument("--through-session",type=int,choices=(1,2),default=1)
    p.add_argument("--epochs",type=int,default=8)
    args=p.parse_args()
    if args.feature_contract:
        print(json.dumps({
            "status":"REQUIRES_SUPERVISOR_20_VS_21_DECISION",
            "feature_version":FEATURE_VERSION,
            "feature_count":len(FEATURE_NAMES),
            "feature_names":FEATURE_NAMES,
            "human_enrollment_authorized":False,
        },indent=2))
        return
    if args.self_test==bool(args.state_dir):
        p.error("choose exactly one of --self-test or --state-dir")
    if args.self_test:
        examples=self_test_examples()
    else:
        bank=SupervisorBank(ROOT/"data"/"supervisor_20261111")
        store=SupervisorSyntheticStore(args.state_dir,bank=bank)
        _check_only_fake(store)
        examples=extract_fictional_training_examples(
            store,through_session=args.through_session,
        )
    result=train_fictional_model(examples,epochs=args.epochs)
    print(json.dumps({
        key:value for key,value in result.items()
        if key not in ("predictions","validation_labels")
    },indent=2))


if __name__=="__main__":
    main()
