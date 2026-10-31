"""Operator commands for the RCT candidate. Default configuration is rehearsal."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import tempfile
import uuid

from src.prototype.rct_candidate import RCTCandidateEngine, policy_record
from src.prototype.rct_candidate_content import ContentBundle, release_report

DEFAULT_SETTINGS = Path("docs/rct_candidate_v1/settings_rehearsal.json")


def deployment(settings):
    return {"allowed_hosts": settings["allowed_hosts"],
            "behind_one_local_tls_proxy": settings.get("behind_one_local_tls_proxy", False)}


def load_settings(path):
    path = Path(path).resolve()
    settings = json.loads(path.read_text(encoding="utf-8"))
    content = settings["content"]
    bundle = ContentBundle(*(path.parent / content[key] for key in
                             ("items", "resources", "fatigue", "information")))
    release = settings.get("release_evidence")
    release = path.parent / release if release else None
    return settings, bundle, release


def engine_from(settings_path, database):
    settings, bundle, release = load_settings(settings_path)
    return RCTCandidateEngine(database, bundle, mode=settings["mode"],
                              simulations=settings["simulations"], control=settings["control"],
                              release_path=release, deployment=deployment(settings))


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    path.chmod(0o600)


def smoke(settings_path, participants=9):
    settings, bundle, release = load_settings(settings_path)
    if settings["mode"] != "rehearsal":
        raise ValueError("smoke requires rehearsal settings")
    if type(participants) is not int or not 9 <= participants <= 60:
        raise ValueError("smoke participant count must be 9..60 fictional journeys")
    from src.prototype.rct_candidate_api import create_app
    with tempfile.TemporaryDirectory(prefix="ijcai_rct_rehearsal_") as temp:
        database = Path(temp) / "rehearsal.sqlite3"
        engine = engine_from(settings_path, database)
        client = create_app(engine).test_client()
        invitations = [engine.issue_invitation() for _ in range(participants)]
        results = []
        for number, invitation in enumerate(invitations):
            headers = {"Authorization": "Bearer " + invitation["invitation"]}
            def post(route, data):
                r = client.post("/api/rct/" + route, json=data, headers=headers)
                if r.status_code != 200:
                    raise AssertionError((route, r.status_code, r.get_json()))
                return r.get_json()
            info = post("information", {})
            post("enroll", dict(agreed=True, information_version=info["information_version"]))
            counts = Counter()
            for step in range(110):
                action = post("next", {})
                if action["action"] == "COMPLETE":
                    break
                assert post("next", {}) == action
                counts[action["stage"]] += 1
                post("rendered", dict(action_id=action["action_id"]))
                if "question" in action:
                    q = action["question"]
                    answer = dict(choice_id=q["options"][(number + step) % len(q["options"])][0])
                elif action["action"] == "FATIGUE":
                    answer = dict(values=[3] * 6)
                else:
                    answer = dict(status="completed")
                payload = dict(request_id=uuid.uuid4().hex, action_id=action["action_id"], response=answer)
                post("act", payload)
                assert post("act", payload)["replayed"]
            else:
                raise AssertionError("journey failed to complete")
            results.append(dict(counts))
        restored = engine_from(settings_path, database)
        assert restored.audit() == engine.audit()
        backup = Path(temp) / "restored.sqlite3"
        engine.backup(backup)
        copy = engine_from(settings_path, backup)
        assert copy.audit() == engine.audit()
        export = engine.export_private()
        arm_counts = Counter(o["assigned_arm"] for o in export["outcomes"])
        assert set(arm_counts) == {"A", "B", "C"}
        assert all(o["pretest_answered"] == o["posttest_answered"] == 16 for o in export["outcomes"])
        per_arm = defaultdict(Counter)
        assigned = {o["pid"]: o["assigned_arm"] for o in export["outcomes"]}
        practices = Counter()
        for row in export["actions"]:
            selected = json.loads(row["selected"])
            per_arm[assigned[row["pid"]]][selected["action"]] += 1
            data = json.loads(row["public"])
            if data["stage"] == "practice" and selected["action"] == "QUESTION":
                practices[row["pid"], data["session"]] += 1
        assert all([practices[o["pid"], s] for s in (1, 2, 3)] == [20, 20, 15] for o in export["outcomes"])
        return dict(software_rehearsal_passed=True, human_enrollment_authorized=False,
                    scope="In-process HTTP test client; does not verify a real browser or public deployment.",
                    fictional_completed=participants, arm_counts=dict(arm_counts),
                    action_counts_by_arm={a: dict(c) for a, c in per_arm.items()},
                    restart_and_backup_restore_passed=True, duplicate_requests_replayed=True,
                    per_participant=dict(pretest=16, practice=[20, 20, 15], fatigue_forms=3, posttest=16),
                    audit=engine.audit())


def make_wsgi_app():
    """For a loopback-bound WSGI server behind the reviewed TLS proxy only."""
    path = os.environ["RCT_SETTINGS"]
    database = os.environ["RCT_DATABASE"]
    settings, _, _ = load_settings(path)
    if settings["mode"] != "live":
        raise ValueError("WSGI live factory requires reviewed live settings")
    from src.prototype.rct_candidate_api import create_app
    return create_app(engine_from(path, database), allowed_hosts=settings["allowed_hosts"],
                      behind_one_local_tls_proxy=settings.get("behind_one_local_tls_proxy", False))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--db", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "check-live", "audit", "export", "backup"):
        p = commands.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("smoke")
    p.add_argument("--participants", type=int, default=9)
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("invite")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--lifetime-hours", type=float, default=72)
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("rotate-invitation")
    p.add_argument("--pid", required=True)
    p.add_argument("--lifetime-hours", type=float, default=72)
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("serve")
    p.add_argument("--port", type=int, default=8077)
    args = parser.parse_args()
    if hasattr(args, "out") and args.out.exists():
        parser.error("output already exists; choose a new path to preserve evidence")
    settings, bundle, release = load_settings(args.settings)
    if args.command in ("preflight", "check-live"):
        report = release_report(bundle, policy_record(settings["simulations"], settings["control"],
                                                       deployment=deployment(settings)), release)
        report["configured_mode"] = settings["mode"]
        save_new(args.out, report)
        print(json.dumps({k: report[k] for k in ("candidate_sha256", "blockers", "mechanical_gate_passed")}, indent=2))
        if args.command == "check-live" and not report["mechanical_gate_passed"]:
            raise SystemExit(2)
        return
    if args.command == "smoke":
        report = smoke(args.settings, args.participants)
        save_new(args.out, report)
        print(json.dumps(report, indent=2))
        return
    if args.db is None:
        parser.error("--db required for this command")
    engine = engine_from(args.settings, args.db)
    if args.command == "invite":
        if not 1 <= args.count <= 1000:
            parser.error("count must be 1..1000")
        # The invitation file is private; no tokens are printed or put in URLs.
        save_new(args.out, [engine.issue_invitation(lifetime_hours=args.lifetime_hours) for _ in range(args.count)])
        print(f"{args.count} private {engine.mode} invitations written to the requested file.")
    elif args.command == "rotate-invitation":
        save_new(args.out, engine.rotate_invitation(args.pid, lifetime_hours=args.lifetime_hours))
    elif args.command == "audit":
        save_new(args.out, engine.audit())
    elif args.command == "export":
        save_new(args.out, engine.export_private())
    elif args.command == "backup":
        print(json.dumps(engine.backup(args.out)))
    elif args.command == "serve":
        if engine.mode != "rehearsal":
            parser.error("Flask development server is rehearsal-only; follow the reviewed WSGI deployment procedure")
        from src.prototype.rct_candidate_api import create_app
        create_app(engine).run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
