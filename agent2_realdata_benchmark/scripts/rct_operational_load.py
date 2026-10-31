"""Rehearsal-only concurrent HTTP workload. Never contacts a public service.

Run from agent2_realdata_benchmark:
python -m scripts.rct_operational_load --participants 30 --workers 8 --out /tmp/rct_load_01.json
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from time import perf_counter
import uuid

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, engine_from
from src.prototype.rct_candidate_api import create_app


def exercise(participants=30, workers=8, settings=DEFAULT_SETTINGS):
    if type(participants) is not int or not 3 <= participants <= 120:
        raise ValueError("participants must be between 3 and 120")
    if type(workers) is not int or not 1 <= workers <= 24:
        raise ValueError("workers must be between 1 and 24")
    config=json.loads(Path(settings).read_text())
    if config.get("mode") != "rehearsal":
        raise ValueError("This tool refuses non-rehearsal settings")
    with TemporaryDirectory(prefix="rct_load_") as directory:
        db=Path(directory)/"study.sqlite3"
        engine=engine_from(settings,db)
        invitations=[engine.issue_invitation()["invitation"] for _ in range(participants)]
        def journey(token):
            client=create_app(engine).test_client()
            headers={"Authorization": "Bearer "+token}
            count=0
            latencies=[]
            def post(route,data):
                started=perf_counter()
                response=client.post("/api/rct/"+route, json=data, headers=headers)
                latencies.append(perf_counter()-started)
                if response.status_code != 200:
                    raise AssertionError((route,response.status_code,response.get_json()))
                return response.get_json()
            info=post("information",{})
            post("enroll",{"agreed":True,"information_version":info["information_version"]})
            for _ in range(120):
                action=post("next",{})
                if action["action"]=="COMPLETE":
                    break
                post("rendered",{"action_id":action["action_id"]})
                if "question" in action:
                    response={"choice_id":action["question"]["options"][0][0]}
                elif action["action"]=="FATIGUE":
                    response={"values":[3]*6}
                else:
                    response={"status":"completed"}
                request={"request_id":uuid.uuid4().hex,"action_id":action["action_id"],"response":response}
                first=post("act",request)
                second=post("act",request)
                assert first["replayed"] is False and second["replayed"] is True
                count+=1
            else:
                raise AssertionError("participant did not complete")
            return count,latencies
        began=perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results=list(executor.map(journey,invitations))
        seconds=perf_counter()-began
        audit=engine.audit()
        counts=Counter(o["assigned_arm"] for o in engine.export_private()["outcomes"])
        assert audit["people"].get("complete")==participants
        assert audit["pending_actions"]==0
        assert set(counts)=={"A","B","C"}
        latencies=[d for _,xs in results for d in xs]
        sorted_l=sorted(latencies)
        return {
            "status":"SYNTHETIC_IN_PROCESS_LOAD_ONLY",
            "actual_network_tls_devices_tested":False,
            "real_people":False,
            "participants":participants,"workers":workers,
            "completed":audit["people"]["complete"],
            "assigned_arm_counts":dict(counts),
            "actions":sum(x for x,_ in results),
            "requests":len(latencies),
            "wall_seconds":round(seconds,3),
            "mean_request_ms":round(mean(latencies)*1000,3),
            "p95_request_ms":round(sorted_l[int(.95*(len(sorted_l)-1))]*1000,3),
            "max_request_ms":round(sorted_l[-1]*1000,3),
            "audit_pending_actions":audit["pending_actions"],
            "limitations":["In-process Flask clients, not Nginx, TLS, Gunicorn or browsers",
                           "Unrealistic instantaneous fictional users; no human think-time",
                           "Do not use observed timing as production capacity certification"],
        }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--participants",type=int,default=30)
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite prior report")
    report=exercise(args.participants,args.workers)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
