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
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sqlite3

RECOVERY_ACTIONS=("CONCEPT_SUMMARY","DROP_2","WORKED_EXAMPLE","SOCRATIC_HINT")
ARMS=("A","B","C")


def analyze(path, *, demo_invite_file=None):
    path=Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("Study database not found: "+str(path))
    # Use SQLite URI mode=ro; no connection to the running Flask application.
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=5) as db:
        db.row_factory=sqlite3.Row
        available={x[0] for x in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "rct_config" not in available:
            raise ValueError("Not a recognized RCT candidate database")
        config=db.execute("SELECT value FROM rct_config WHERE id=1").fetchone()
        if config is None:
            raise ValueError("Not a recognized RCT candidate database")
        settings=json.loads(config["value"])
        if settings.get("mode")!="rehearsal":
            raise ValueError("Refusing to inspect potentially real-participant data")
        if not {"rct_actions","rct_people","rct_events"}.issubset(available):
            raise ValueError("Incomplete rehearsal database schema")
        rows=db.execute(
            "SELECT a.pid,a.selected,a.public,a.rendered_at,a.completed_at,a.response,"
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
        selected_demo_participant = None
        if demo_invite_file is not None:
            # The private invitation file is read locally and never returned,
            # printed, or stored. The hash binds it to this rehearsal database.
            demonstration = json.loads(
                Path(demo_invite_file).expanduser().read_text(encoding="utf-8")
            )
            if demonstration.get("purpose") != "FICTIONAL_OPERATOR_SELECTED_ARM_A_BROWSER_DEMO_ONLY":
                raise ValueError("Not an operator-selected fictional Arm-A invitation")
            pid = demonstration.get("participant_id")
            token = demonstration.get("invitation")
            if not isinstance(pid, str) or not isinstance(token, str):
                raise ValueError("Malformed private demonstration invitation")
            matched = db.execute(
                "SELECT state,status,token_hash FROM rct_people WHERE pid=?", (pid,)
            ).fetchone()
            if matched is None or not hmac.compare_digest(
                matched["token_hash"], sha256(token.encode()).hexdigest()
            ):
                raise ValueError("Private invitation does not belong to this rehearsal database")
            state = json.loads(matched["state"]) if matched["state"] else {}
            if state.get("arm") != "A":
                raise ValueError("Selected participant is not assigned to Arm A")
            chosen_actions = [row for row in rows if row["pid"] == pid]
            offered_in_stages = Counter()
            completed_in_stages = Counter()
            selected_recovery = Counter()
            rendered_recovery = Counter()
            root_decisions = 0
            socratic_root_visited = 0
            resource_concepts = []
            for row in chosen_actions:
                action = json.loads(row["selected"])
                public = json.loads(row["public"])
                stage_name = public["stage"]
                offered_in_stages[stage_name] += 1
                if row["completed_at"] is not None:
                    completed_in_stages[stage_name] += 1
                if action["action"] in RECOVERY_ACTIONS:
                    selected_recovery[action["action"]] += 1
                    resource_concepts.append(dict(
                        action=action["action"], concept=action["concept"]
                    ))
                    if row["rendered_at"] is not None:
                        rendered_recovery[action["action"]] += 1
                trace = action.get("planning_trace")
                if trace and stage_name == "practice":
                    root_decisions += 1
                    if any(
                        visits > 0 for key, visits in trace.get("root_visits", {}).items()
                        if key.startswith("SOCRATIC_HINT::")
                    ):
                        socratic_root_visited += 1
            selected_demo_participant = dict(
                verified_private_demo_invitation=True,
                arm="A",
                status=matched["status"],
                stage=state.get("stage"),
                session=state.get("session"),
                question_index=state.get("index"),
                pending_action=bool(state.get("pending")),
                offered_actions_by_stage=dict(offered_in_stages),
                completed_actions_by_stage=dict(completed_in_stages),
                selected_resources_by_kind=dict(selected_recovery),
                rendered_resources_by_kind=dict(rendered_recovery),
                selected_resource_sequence=resource_concepts,
                pomcp_root_decisions=root_decisions,
                socratic_actions_explored_at_root=socratic_root_visited,
                private_invitation_code_disclosed=False,
            )
        return dict(
            evidence="LOCAL_REHEARSAL_READ_ONLY",
            participant_records=len(persons),
            enrolled_by_arm=dict(per_arm),
            latest_enrollment=newest,
            latest_enrollment_scope="Last enrolled in entire database; not necessarily browser-demo participant",
            selected_demo_participant=selected_demo_participant,
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
    parser.add_argument("--demo-invite-file",type=Path,
                        help="Private operator-selected Arm A invitation; never printed")
    args=parser.parse_args()
    result=analyze(args.db,demo_invite_file=args.demo_invite_file)
    print(json.dumps(result,indent=2))
    if args.out is not None:
        if args.out.exists():
            raise FileExistsError("Refusing to overwrite an earlier diagnostic report")
        args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
