"""Read-only RCT rehearsal resource-selection audit; no invitation codes, no mutations.

Usage (from agent2_realdata_benchmark):
python -m scripts.rct_resource_diagnostic \
    --db "$HOME/ijcai_rct_video_demo/demo.sqlite3"

The report describes actions that actually occurred in this one local database.
It does not infer that any missing action is unreachable, or estimate clinical
or educational effectiveness. Refuses live-mode / unrecognized databases.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3

RECOVERY_ACTIONS=("CONCEPT_SUMMARY","DROP_2","WORKED_EXAMPLE","SOCRATIC_HINT")
ARMS=("A","B","C")


def analyze(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("Study database not found: "+str(path))
    # Use SQLite URI mode=ro; no connection to the running Flask application.
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=5) as db:
        db.row_factory=sqlite3.Row
        config=db.execute(
            "SELECT value FROM sqlite_master JOIN rct_config ON 1=1 "
            "WHERE sqlite_master.name='rct_config' AND rct_config.id=1"
        ).fetchone()
        if config is None:
            raise ValueError("Not a recognized RCT candidate database")
        settings=json.loads(config["value"])
        if settings.get("mode")!="rehearsal":
            raise ValueError("Refusing to inspect potentially real-participant data")
        rows=db.execute(
            "SELECT a.selected,a.public,a.rendered_at,a.completed_at,a.response,"
            "p.state,p.status FROM rct_actions a "
            "JOIN rct_people p ON p.pid=a.pid ORDER BY a.offered_at,a.id"
        ).fetchall()
        persons=db.execute("SELECT state,status FROM rct_people").fetchall()
        latest=db.execute(
            "SELECT p.state,p.status FROM rct_people p "
            "JOIN rct_events e ON e.pid=p.pid "
            "WHERE e.kind='enrolled' ORDER BY e.seq DESC LIMIT 1"
        ).fetchone()
        per_arm=Counter()
        per_arm_resource=defaultdict(Counter)
        offered=Counter()
        delivered=Counter()
        response=Counter()
        stage=Counter()
        planner_steps=0
        socratic_considered=0
        socratic_root_values=[]
        for row in rows:
            state=json.loads(row["state"]) if row["state"] else {}
            selected=json.loads(row["selected"])
            public=json.loads(row["public"])
            arm=state.get("arm","not_enrolled")
            kind=selected["action"]
            stage[public["stage"]]+=1
            if kind in RECOVERY_ACTIONS:
                offered[kind]+=1
                per_arm_resource[arm][kind]+=1
                if row["rendered_at"] is not None:
                    delivered[kind]+=1
                if row["response"]:
                    answer=json.loads(row["response"])
                    response[kind+"_"+answer.get("response",{}).get("status","answered")]+=1
            plan=selected.get("planning_trace")
            if arm=="A" and public["stage"]=="practice" and plan:
                planner_steps+=1
                root_values=plan.get("root_values",{})
                socratic=[v for k,v in root_values.items()
                          if k.startswith("SOCRATIC_HINT::") and v is not None]
                if socratic:
                    socratic_considered+=1
                    socratic_root_values.append(max(socratic))
        for p in persons:
            if p["state"]:
                state=json.loads(p["state"])
                arm=state.get("arm","unknown")
                if arm not in ARMS:
                    raise ValueError("Unexpected assignment arm in fictional database")
                per_arm[arm]+=1
        newest=None
        if latest is not None and latest["state"]:
            x=json.loads(latest["state"])
            newest=dict(
                arm=x.get("arm"),
                status=latest["status"],
                stage=x.get("stage"),
                session=x.get("session"),
                question_index=x.get("index"),
                resources_spent_current_session=x.get("recovery",{}).get("pomcp_resource_spent",0),
            )
        return dict(
            evidence="LOCAL_REHEARSAL_READ_ONLY",
            participant_records=len(persons),
            enrolled_by_arm=dict(per_arm),
            latest_enrollment=newest,
            offered_actions_by_stage=dict(stage),
            all_resources_offered=dict(offered),
            rendered_resources=dict(delivered),
            resource_responses=dict(response),
            resources_by_arm={arm:dict(per_arm_resource.get(arm,{})) for arm in ARMS},
            arm_A_POMCP_root_decisions=planner_steps,
            socratic_in_POMCP_root_estimates=socratic_considered,
            max_socratic_root_value=max(socratic_root_values) if socratic_root_values else None,
            no_Socratic_hint_interpretation=(
                "SOCRATIC_HINT is an available action, not a guaranteed 4th step. "
                "Only arm A during practice can select a resource; its first "
                "practice action per session is always a question, and at most "
                "two resources per session may be selected. "
                "No hints observed cannot distinguish nonselection from a "
                "defective policy without root estimates and controlled trials."
            ),
            disclaimer="Operator-only fictional data; no token hashes, invitations or participant IDs exported.",
        )


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--out",type=Path,help="Optional new JSON file, not an existing one")
    args=parser.parse_args()
    result=analyze(args.db)
    print(json.dumps(result,indent=2))
    if args.out is not None:
        if args.out.exists():
            raise FileExistsError("Refusing to overwrite an earlier diagnostic report")
        args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
