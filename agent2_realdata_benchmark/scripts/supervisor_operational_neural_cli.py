"""OFFLINE authorized BKT vs neural evaluation; no enrollment or model serving.

A PI-signed feature contract is mandatory. The original brief lists 20
actual features but one line says 21; never invent the unlisted feature.
Run outside the public Gunicorn server with the institutionally approved
pseudonymous research database. DKT requires independently evaluated,
event-ID-aligned heldout predictions supplied by the approved DKT pipeline.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess

from src.prototype.supervisor_neural_training import FEATURE_NAMES
from src.prototype.supervisor_operational_neural import (
    extract_examples, train_and_compare,
)


def verified_feature_contract(doc: Path, signature: Path, key: Path):
    for item in (doc,signature,key):
        if not item.is_absolute() or not item.is_file() or item.is_symlink():
            raise ValueError("existing nonsymlink absolute approval files required")
    verified=subprocess.run(
        ["openssl","dgst","-sha256","-verify",str(key),
         "-signature",str(signature),str(doc)],
        capture_output=True,text=True,timeout=15,
    )
    if verified.returncode:
        raise ValueError("independently supplied PI signature cannot be verified")
    payload=json.loads(doc.read_text(encoding="utf-8"))
    if (type(payload) is not dict
        or payload.get("schema")!="SUPERVISOR_NN_FEATURE_CONTRACT_V1"
        or payload.get("decision")!="approved"
        or payload.get("feature_count")!=20
        or payload.get("feature_names")!=list(FEATURE_NAMES)
        or type(payload.get("reviewer")) is not str
        or len(payload["reviewer"].strip())<3
        or type(payload.get("institutional_data_use_reference")) is not str
        or not payload["institutional_data_use_reference"].strip()):
        raise ValueError("PI must resolve the exact 20-vs-21 feature contract")
    try:
        date=datetime.fromisoformat(payload["approved_at"])
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError("timezone-aware approval date required")
    except (ValueError,KeyError,TypeError):
        raise ValueError("timezone-aware approval date required") from None
    return payload


def load_dkt(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("approved DKT predictions CSV required")
    predictions={}
    with path.open(encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=["event_id","probability_correct"]:
            raise ValueError("DKT CSV must contain exact event_id,probability_correct columns")
        for row in reader:
            event=int(row["event_id"])
            if event in predictions or event<1:
                raise ValueError("duplicate or invalid DKT event id")
            predictions[event]=float(row["probability_correct"])
    return predictions


def save_private(path: Path, result):
    if not path.is_absolute() or path.is_symlink() or path.exists():
        raise ValueError("new absolute nonsymlink result destination required")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("existing private output directory required")
    old_umask=os.umask(0o077)
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(result,f,indent=2,sort_keys=True)
            f.write("\n")
    finally:
        os.umask(old_umask)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research-db",type=Path,required=True)
    p.add_argument("--through-session",type=int,choices=(1,2),required=True)
    p.add_argument("--feature-approval",type=Path,required=True)
    p.add_argument("--signature",type=Path,required=True)
    p.add_argument("--public-key",type=Path,required=True)
    p.add_argument("--epochs",type=int,default=8)
    p.add_argument("--dkt-predictions",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    verified_feature_contract(args.feature_approval,args.signature,args.public_key)
    examples=extract_examples(args.research_db,through_session=args.through_session)
    dkt=load_dkt(args.dkt_predictions) if args.dkt_predictions else None
    result=train_and_compare(examples,epochs=args.epochs,dkt_predictions=dkt)
    result["scope"]="PI-SIGNED_RESEARCH_ONLY_NO_PARTICIPANT_INTERVENTION"
    save_private(args.output,result)
    print("Research-only comparison saved to a new mode-0600 file.")
    print("Training participants:",result["n_train_students"],
          "| Heldout participants:",result["n_validation_students"])
    print("No personal contact information processed or printed.")
    print("No experimental arm assignment or live learning policy changed.")


if __name__=="__main__":
    main()
