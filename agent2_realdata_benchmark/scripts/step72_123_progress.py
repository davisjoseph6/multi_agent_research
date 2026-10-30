"""Display a TRANSPARENT subjective task-equivalent completion proxy.

Never interpret it as scientific readiness, publication likelihood, or approval.
"""
import csv
import json
from pathlib import Path
from collections import Counter

CREDIT = {
    'SYNTHETIC-IMPLEMENTED': 1.0,
    'PARTIAL': 0.5,
    'EXTERNAL-REQUIRED': 0.0,
    'NOT-PROVEN': 0.0,
}


def summarize(rows):
    if len(rows) != 52 or {int(x['step']) for x in rows} != set(range(72,124)):
        raise ValueError('Exactly one row for every Step 72–123 is required')
    if any(x['evidence_status'] not in CREDIT for x in rows):
        raise ValueError('Unknown status')
    if any(float(x['evidence_credit']) != CREDIT[x['evidence_status']] for x in rows):
        raise ValueError('Unjustified evidence credit; edit status only with supporting evidence')
    counts = Counter(x['evidence_status'] for x in rows)
    points = sum(CREDIT[x['evidence_status']] for x in rows)
    return {
        'denominator_steps': 52,
        'status_counts': dict(counts),
        'task_equivalent_points': points,
        'provisional_percentage': round(points / 52 * 100, 1),
        'scoring_rubric': CREDIT,
        'synthetic_testbed_is_not_human_study': True,
        'human_study_authorized': False,
        'scientific_completion_certified': False,
    }


def main():
    path = Path('docs/steps72_123_closure_register.csv')
    with path.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(summarize(rows), indent=2))


if __name__ == '__main__':
    main()
