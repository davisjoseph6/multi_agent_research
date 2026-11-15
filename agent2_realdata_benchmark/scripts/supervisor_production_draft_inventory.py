"""Create a PRIVATE, strictly NON-APPROVED production review work package.

No secrets, signatures, participant data, database mutations, HTTP services,
Graph requests, production DNS, or human enrollment are created by this tool.
Final institutional artifacts replace these placeholders; they are never
treated as signed approvals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat

from src.prototype.pilot_release_evidence_gate import (
    GATES, SCHEMA, inspect_evidence_index,
)
from scripts.supervisor_content_approval_template import build_inventory, ROOT

SHA = re.compile(r"[0-9a-f]{40}\Z")


def _private_file(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(value)
    os.chmod(path, 0o600)


def _json(path: Path, value: dict) -> None:
    _private_file(path, json.dumps(value, indent=2, sort_keys=True,
                                   ensure_ascii=False) + "\n")


def scaffold(output: Path, commit: str) -> dict:
    """Build draft inventory without granting approval or creating fake PDFs."""
    if not SHA.fullmatch(commit):
        raise ValueError("exact lower-case 40-character source commit required")
    if not output.is_absolute() or output.is_symlink() or output.exists():
        raise ValueError("new, absolute, unoccupied private directory required")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("trusted existing non-symlink parent directory required")
    prior = os.umask(0o077)
    try:
        output.mkdir(mode=0o700)
        (output / "evidence").mkdir(mode=0o700)
        (output / "notices").mkdir(mode=0o700)
        (output / "configuration").mkdir(mode=0o700)
        index = {
            "schema_version": SCHEMA,
            "candidate_commit": commit,
            "records": {},
        }
        for name, role in GATES.items():
            index["records"][name] = {
                "status": "pending",
                "reviewer_role": role,
                "reviewer": "",
                "reviewed_at": None,
                "sha256": None,
                "path": f"evidence/{name}.pdf",
            }
            _private_file(output / "evidence" / f"{name}.DRAFT.md",
                          f"# {name}\n\nDRAFT ONLY / NOT APPROVED.\n"
                          f"Required independent reviewer role: {role}.\n"
                          "Replace with authentic reviewed evidence PDF; "
                          "then enter its exact relative path, SHA-256, reviewer "
                          "and timezone-aware review date in evidence_index.json.\n")
        _json(output / "evidence_index.json", index)
        content = build_inventory(ROOT, commit)
        _json(output / "content_review_PENDING.json", content)
        _private_file(output / "notices" / "recruitment_notice_en_DRAFT.md",
                      "# Recruitment privacy notice — English\n\n"
                      "DRAFT / NOT APPROVED / NOT FOR PARTICIPANTS.\n\n"
                      "- Data controller / joint-controller: [INSTITUTIONAL REVIEW]\n"
                      "- Responsible investigator and study contact: [REVIEW]\n"
                      "- DPO / privacy rights contact: [REVIEW]\n"
                      "- Purpose(s) of recruitment and research: [REVIEW]\n"
                      "- Legal basis and any special-category data conditions: [REVIEW]\n"
                      "- Categories of data collected: [REVIEW]\n"
                      "- Voluntary participation, consent/withdrawal procedure: [REVIEW]\n"
                      "- Access recipients / researcher roles: [REVIEW]\n"
                      "- Hosting, subprocessors and international transfers: [REVIEW]\n"
                      "- Retention, erasure schedule and deletion process: [REVIEW]\n"
                      "- Data subject rights and supervisory authority: [REVIEW]\n"
                      "- AI-points eligibility and contact policy (if approved): [REVIEW]\n"
                      "- Version, date and independent approval details: [REVIEW]\n\n"
                      "Replace with the final approved/signed PDF.\n")
        _private_file(output / "notices" / "recruitment_notice_fr_DRAFT.md",
                      "# Notice d'information pour le recrutement — Français\n\n"
                      "BROUILLON / NON APPROUVÉ / NON DESTINÉ AUX PARTICIPANTS.\n\n"
                      "- Responsable(s) du traitement : [VALIDATION REQUISE]\n"
                      "- Responsable scientifique et contact de l'étude : [VALIDATION]\n"
                      "- DPO / contact pour les droits : [VALIDATION]\n"
                      "- Finalités du recrutement et de la recherche : [VALIDATION]\n"
                      "- Base légale et données sensibles éventuelles : [VALIDATION]\n"
                      "- Catégories de données recueillies : [VALIDATION]\n"
                      "- Participation volontaire, consentement et retrait : [VALIDATION]\n"
                      "- Destinataires et accès des chercheurs : [VALIDATION]\n"
                      "- Hébergement, sous-traitants et transferts internationaux : [VALIDATION]\n"
                      "- Conservation, effacement et procédure de suppression : [VALIDATION]\n"
                      "- Droits des personnes et autorité de contrôle : [VALIDATION]\n"
                      "- Conditions d'attribution des points IA, si approuvées : [VALIDATION]\n"
                      "- Version, date et approbation indépendante : [VALIDATION]\n\n"
                      "Remplacer par le PDF final approuvé et signé.\n")
        _private_file(output / "configuration" / "live.env.template",
                      "# EXAMPLE ONLY — NOT A RUNNABLE PRODUCTION ENVIRONMENT.\n"
                      "# NEVER source or install this file; keep all actual secrets out of Git.\n"
                      "SUPERVISOR_VPS_MODE=staging\n"
                      "SUPERVISOR_MAIL_TRANSPORT=disabled\n"
                      "# For the future signed LIVE env, IT must supply:\n"
                      "# SUPERVISOR_VPS_MODE=live\n"
                      "# SUPERVISOR_VPS_ROOT=/var/lib/ijcai-supervisor-live\n"
                      "# SUPERVISOR_VPS_COMMIT=<EXACT_SIGNED_COMMIT>\n"
                      "# SUPERVISOR_VPS_HOST=<APPROVED_NON_DEMO_HOST>\n"
                      "# SUPERVISOR_RECRUITMENT_HOST=<APPROVED_NON_DEMO_HOST>\n"
                      "# SUPERVISOR_INSTITUTION_PUBLIC_KEY=<TRUSTED_KEY>\n"
                      "# SUPERVISOR_INSTITUTION_SIGNATURE=<REAL_SIGNATURE>\n"
                      "# SUPERVISOR_RELEASE_EVIDENCE=<SIGNED_EVIDENCE_MANIFEST>\n"
                      "# SUPERVISOR_CONTENT_APPROVAL=<SIGNED_CONTENT_MANIFEST>\n"
                      "# SUPERVISOR_CONTENT_SIGNATURE=<REAL_PI_SIGNATURE>\n"
                      "# SUPERVISOR_RECRUITMENT_NOTICE_EN=<APPROVED_PDF>\n"
                      "# SUPERVISOR_RECRUITMENT_NOTICE_FR=<APPROVED_PDF>\n"
                      "# SUPERVISOR_RECRUITMENT_NOTICE_SIGNATURE_EN=<REAL_SIGNATURE>\n"
                      "# SUPERVISOR_RECRUITMENT_NOTICE_SIGNATURE_FR=<REAL_SIGNATURE>\n"
                      "# SUPERVISOR_MAIL_TRANSPORT=microsoft_graph\n"
                      "# SUPERVISOR_GRAPH_TENANT_ID=<ENTRA_TENANT_GUID>\n"
                      "# SUPERVISOR_GRAPH_CLIENT_ID=<APP_CLIENT_GUID>\n"
                      "# SUPERVISOR_GRAPH_CLIENT_SECRET=<PRIVATE_VAULT_VALUE>\n"
                      "# SUPERVISOR_GRAPH_SENDER_EMAIL=davis.joseph@aivancity.education\n"
                      "# SUPERVISOR_INTAKE_RATE_SECRET=<PRIVATE_RANDOM_32PLUS_BYTES>\n"
                      "# SUPERVISOR_PROGRAMS=<APPROVED_PIPE_DELIMITED_PROGRAMS>\n")
        _private_file(output / "README_REPLACE_AND_REVIEW.txt",
                      "NOT PRODUCTION AUTHORIZATION. NO PLACEHOLDER MAY BE SIGNED AS APPROVED.\n"
                      "1. Obtain 14 real evidence PDFs; fill evidence_index.json "
                      "with exact hashes, names and review times.\n"
                      "2. Replace provisional in-repository Annex/teaching text "
                      "with final approved content, commit and rerun the content "
                      "inventory against that exact source SHA.\n"
                      "3. Obtain independent PI content approval, institution "
                      "release signature and English/French PDF notice signatures.\n"
                      "4. Have the authorized administrator verify the public "
                      "key out-of-band; never create a substitute institutional key.\n"
                      "5. Provision a separate LIVE environment and database, "
                      "approved DNS/TLS, scoped Graph sender and recovery tests.\n"
                      "6. Re-run independent signed-release checks. Only then "
                      "can live services be installed by authorized operators.\n")
    finally:
        os.umask(prior)
    return {"drafts_created": True, "approval_status": "PENDING",
            "evidence_categories": len(GATES),
            "human_enrollment_authorized": False,
            "mail_enabled": False}


def inspect(output: Path) -> dict:
    if not output.is_absolute() or output.is_symlink() or not output.is_dir():
        raise ValueError("existing private review package required")
    if stat.S_IMODE(output.stat().st_mode) != 0o700:
        raise ValueError("review directory must remain mode 0700")
    result = inspect_evidence_index(output / "evidence_index.json")
    review_path = output / "content_review_PENDING.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    return {"evidence": result["gates_complete"],
            "evidence_required": result["gates_required"],
            "content_review_decision": review.get("decision"),
            "content_issues": review.get("blocking_issues", []),
            "human_enrollment_authorized": False,
            "release_signature_verified": False,
            "note": "Inventory only; independent signatures require separate verification."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scaffold", type=Path, metavar="NEW_PRIVATE_DIR")
    group.add_argument("--check", type=Path, metavar="PRIVATE_DIR")
    parser.add_argument("--commit", help="exact release candidate SHA; required with --scaffold")
    args = parser.parse_args()
    if args.scaffold:
        if not args.commit:
            parser.error("--scaffold requires --commit")
        value = scaffold(args.scaffold, args.commit)
    else:
        if args.commit:
            parser.error("--check does not take --commit")
        value = inspect(args.check)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
