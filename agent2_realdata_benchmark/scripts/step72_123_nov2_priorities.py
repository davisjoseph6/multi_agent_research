"""Read-only, original-exit-criteria-based 52-step triage. No status changes."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from collections import Counter

PRIORITIES = {
    "P0 — scientific validity and novelty": set((72,73,74,78,79,80,81,83,85,86,88,93,94,95)),
    "P1 — independent educational readiness": set(range(96,107)),
    "P1 — experimental software and privacy": set((103,106,117,118,119,120,121,122,123)),
}
ORDERED = [
    "P0 — scientific validity and novelty",
    "P1 — independent educational readiness",
    "P1 — experimental software and privacy",
    "P2 — remaining requirements",
]
CREDIT = {"SYNTHETIC-IMPLEMENTED": 1.0, "PARTIAL": .5, "EXTERNAL-REQUIRED": 0., "NOT-PROVEN": 0.}


def audit(path: Path) -> dict:
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'step','requirement','evidence_status','evidence_credit','exit_criterion','independent_signoff'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Register columns missing; refuse to score a different schema')
        rows = list(reader)
    if len(rows)!=52 or {int(r['step']) for r in rows}!=set(range(72,124)):
        raise ValueError('Register must contain exactly Steps 72–123 once each')
    groups={k:[] for k in ORDERED}
    counts=Counter()
    closure_anomalies=[]
    score=0.
    for r in sorted(rows, key=lambda x:int(x['step'])):
        stat=r['evidence_status']
        if stat not in CREDIT: raise ValueError(f'Unknown evidence status: {stat}')
        if abs(float(r['evidence_credit']) - CREDIT[stat])>1e-7:
            raise ValueError(f'Nonstandard evidence credit for step {r["step"]}')
        score+=CREDIT[stat]
        counts[stat]+=1
        if stat=='SYNTHETIC-IMPLEMENTED' and r['independent_signoff'].strip().upper() in ('NOT RECEIVED','PENDING',''):
            closure_anomalies.append({'step':int(r['step']), 'requirement':r['requirement'],
              'status':stat, 'missing_signoff':True,'original_exit_criterion':r['exit_criterion']})
        if stat=='SYNTHETIC-IMPLEMENTED':
            continue
        step=int(r['step'])
        dest=next((k for k in ORDERED if step in PRIORITIES.get(k,set())), ORDERED[-1])
        groups[dest].append({
            'step':step,'requirement':r['requirement'],'status':stat,
            'exit_criterion':r['exit_criterion'],
            'signoff':r['independent_signoff'],
        })
    return {'denominator_steps':52,'score_proxy_points':score,
            'provisional_percentage':round(100*score/52,1),
            'synthetic_evidence_not_human_study':True,
            'scientific_completion_certified':False,
            'status_counts':dict(counts),
            'synthetic_implemented_rows_without_signoff':closure_anomalies,
            'remaining_original_exit_criteria':groups,
            'original_step_rows_not_modified':True,
            'critical_limit':'Cannot change completion statuses without full original exit-criterion evidence, real independent signoff when required.'}


def markdown(report: dict) -> str:
    lines=["# IJCAI 2027 — 52-step evidence-first Nov 2 sprint", "",
           f"**Provisional rubric:** {report['score_proxy_points']} / 52 = {report['provisional_percentage']}%. ",
           "This is not scientific publication readiness or human-study authorization.", "",
           "Only existing original register rows are interpreted. No evidence status was upgraded.",""]
    for group, items in report['remaining_original_exit_criteria'].items():
        lines += [f"## {group}", ""]
        for item in items:
            lines += [f"### Step {item['step']} — {item['requirement']} ({item['status']})",
                      f"**Exact exit criterion:** {item['exit_criterion']}",
                      f"**Independent signoff:** {item['signoff']}", ""]
    lines += ["## Important: synthetic-credit rows with missing signoff", "",
              "These rows have credit in the historical rubric but their final signed exit criteria remain unverified:",""]
    for row in report['synthetic_implemented_rows_without_signoff']:
        lines.append(f"- Step {row['step']}: {row['requirement']} — {row['original_exit_criterion']}")
    lines += ["","## Stop conditions", "",
              "- Do not change statuses to `SYNTHETIC-IMPLEMENTED` merely because tests pass.",
              "- Do not use Phase 6 frozen test outcomes to choose models or revise specifications.",
              "- Do not call already-explored Phase 6 validation a fresh confirmatory holdout.",
              "- No actual participant recruitment until ethics, privacy and institutional approvals.",
              "- No invented educational review dates, records or psychometric validity.",
              "- No claim of causal recovery benefit from BKT response prediction.", ""]
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--register',type=Path,default=Path('docs/steps72_123_closure_register.csv'))
    p.add_argument('--out',type=Path,default=Path('/tmp/ijcai_nov2_remaining_exit_criteria.md'))
    args=p.parse_args()
    if args.out.exists(): p.error('Refusing to overwrite existing evidence report')
    result=audit(args.register)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(markdown(result),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='remaining_original_exit_criteria'},indent=2))
    print('Unresolved original exit criteria:',sum(len(x) for x in result['remaining_original_exit_criteria'].values()))
    print('Read-only report:',args.out)

if __name__=='__main__':main()
