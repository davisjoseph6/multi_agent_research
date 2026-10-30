"""Offline, privacy-minimizing real-data predictive benchmark, DEVELOPMENT ONLY.

Intended for the corrected ASSISTments 2009-10 Skill Builder CSV supplied
locally by the authorized researcher. The script does NOT fetch, export or
redistribute student records, does NOT use real held-out students for scoring,
and makes NO counterfactual intervention/forgetting detection claims.

Uses the exact committed src.prototype.step95_bayesian_forgetting_filter.
No external dependencies. No PII/student identifiers in output JSON.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from hashlib import sha256
import itertools
import json
from math import log
from pathlib import Path

from src.prototype.step95_bayesian_forgetting_filter import Model, TwoStateFilter

SPLIT_SALT = 'ijcai27_assist09_student_dev_predeclared_v1'
GRIDS = {
    'no_forgetting': tuple((slip, guess, learn, 0.0)
        for slip, guess, learn in itertools.product((.1, .2), (.1, .25), (.08, .2))),
    'with_forgetting': tuple((slip, guess, learn, forget)
        for slip, guess, learn, forget in itertools.product((.1, .2), (.1, .25), (.08, .2), (.01, .03, .08))),
}
INITIAL_MASTERY = .25


def stable_split(student_id: str) -> str:
    """All records of a student must occupy the same split."""
    key = (SPLIT_SALT + '\0' + student_id).encode('utf-8')
    b = int.from_bytes(sha256(key).digest()[:8], 'big') % 100
    return 'train' if b < 60 else 'development' if b < 80 else 'sealed_test'


def source_hash(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Event:
    order: int
    correct: bool


def load_local_data(path: Path, *, require_min_students=10) -> dict:
    if not path.is_file() or path.suffix.lower() != '.csv':
        raise ValueError('Supply a local, authorized .csv file')
    by_split = {s: defaultdict(list) for s in ('train', 'development', 'sealed_test')}
    students = {s: set() for s in by_split}
    seen_order = set()
    skipped_no_skill = 0
    count = 0
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('Missing CSV header')
        id_field = next((f for f in ('user_id', 'student_id') if f in reader.fieldnames), None)
        skill_field = next((f for f in ('skill_id', 'skill_name') if f in reader.fieldnames), None)
        order_field = next((f for f in ('order_id', 'problem_log_id') if f in reader.fieldnames), None)
        if not (id_field and skill_field and order_field and 'correct' in reader.fieldnames):
            raise ValueError('Required columns: user_id/student_id, skill_id/skill_name, order_id/problem_log_id, correct')
        for row_num, row in enumerate(reader, 2):
            sid = (row.get(id_field) or '').strip()
            skill = (row.get(skill_field) or '').strip()
            correct = (row.get('correct') or '').strip()
            order = (row.get(order_field) or '').strip()
            if not sid or not order:
                raise ValueError(f'Invalid required identifier or order at CSV row {row_num}')
            if not skill or skill.lower() in ('nan', 'null', 'none'):
                skipped_no_skill += 1
                continue
            if correct not in ('0', '1', '0.0', '1.0'):
                raise ValueError(f'Unexpected binary correct value at CSV row {row_num}')
            try:
                order_value = int(order)
            except ValueError as exc:
                raise ValueError(f'Non-integer chronological order at CSV row {row_num}') from exc
            # Preserve true original rows only if explicitly flagged, excluding
            # scaffolds; do not infer treatment from hints/correctness.
            if 'original' in row and (row['original'] or '').strip() not in ('1', '1.0', ''):
                continue
            key = (sid, skill, order_value)
            if key in seen_order:
                raise ValueError('Repeated student-skill-order event; use corrected, deduplicated release')
            seen_order.add(key)
            split = stable_split(sid)
            by_split[split][(sid, skill)].append(Event(order_value, correct in ('1', '1.0')))
            students[split].add(sid)
            count += 1
    if not count:
        raise ValueError('No eligible events')
    for label in ('train', 'development'):
        if len(students[label]) < require_min_students:
            raise ValueError(f'Insufficient distinct students in {label}; need {require_min_students}')
    for records in by_split.values():
        for events in records.values():
            events.sort(key=lambda e: e.order)
    return {'groups': by_split, 'students': students, 'events': count,
            'skipped_missing_skill': skipped_no_skill}


def grouped_scores(groups: dict, model: tuple[float, float, float, float] | None,
                   constant: float | None = None) -> dict:
    if (model is None) == (constant is None):
        raise ValueError('Give model or constant')
    totals = defaultdict(lambda: [0.0, 0.0, 0])
    for (student, _skill), events in sorted(groups.items()):
        flt = TwoStateFilter(Model(model[0], model[1], model[3]), INITIAL_MASTERY) if model else None
        for e in events:
            p = (flt.mastery * (1-model[0]) + (1-flt.mastery) * model[1]) if flt else constant
            p = min(1 - 1e-12, max(1e-12, p))
            y = int(e.correct)
            s = totals[student]
            s[0] += (p - y) ** 2
            s[1] += -(y * log(p) + (1-y) * log(1-p))
            s[2] += 1
            if flt:
                flt.step(e.correct, learn=model[2])
    n = sum(totals[k][2] for k in sorted(totals))
    if not n: raise ValueError('No evaluated observations')
    return {'brier': sum(totals[k][0] for k in sorted(totals))/n,
            'log_loss': sum(totals[k][1] for k in sorted(totals))/n,
            'n_observations': n, 'n_students': len(totals),
            '_by_student': dict(totals)}


def stripped(s: dict) -> dict:
    return {k:v for k,v in s.items() if not k.startswith('_')}


def paired_bootstrap(a: dict, b: dict, *, key: int, n_reps=1000) -> dict:
    import random
    # Student-cluster bootstrap avoids pretending within-student responses
    # are independent; still descriptive because policy/grid is exploratory.
    x, y = a['_by_student'], b['_by_student']
    if set(x) != set(y): raise AssertionError('Mismatched subjects in paired contrast')
    ids = sorted(x)
    rng = random.Random(key)
    deltas = []
    for _ in range(n_reps):
        sampled = rng.choices(ids, k=len(ids))
        num_a = sum(x[i][0] for i in sampled)
        num_b = sum(y[i][0] for i in sampled)
        denom = sum(x[i][2] for i in sampled)
        deltas.append((num_a - num_b) / denom)
    deltas.sort()
    return {'brier_difference': a['brier'] - b['brier'],
            'descriptive_student_cluster_bootstrap_95pct_interval': [deltas[int(.025*n_reps)], deltas[int(.975*n_reps)-1]]}


def benchmark(path: Path, *, require_min_students=10) -> dict:
    content = load_local_data(path, require_min_students=require_min_students)
    train = content['groups']['train']
    development = content['groups']['development']
    n_train = sum(len(e) for e in train.values())
    train_correct = sum(sum(e.correct for e in events) for events in train.values())
    constant = min(.999999, max(.000001, train_correct / n_train))
    best_models = {}
    for family, grid in GRIDS.items():
        fitted = sorted((grouped_scores(train, model=x)['log_loss'], x) for x in grid)
        best_models[family] = fitted[0][1]
    scores = {'train_prevalence_constant': grouped_scores(development, None, constant)}
    for family, model in best_models.items():
        scores[family] = grouped_scores(development, model)
    return {
        'status': 'REAL OBSERVATIONAL DATA, DEVELOPMENT SPLIT ONLY',
        'dataset_sha256': source_hash(path),
        'dataset_name': 'user-supplied authorized local data (no raw student records exported)',
        'dataset_source': 'ASSISTments corrected 2009-10 Skill Builder, if this source was actually used',
        'model': 'committed TwoStateFilter, common fixed-parameter grid, updates after each observed response',
        'split_protocol': 'hashed student disjoint 60/20/20; last 20% SEALED and never evaluated by this script',
        'train_only_parameter_selection': True,
        'skill_handling': 'per-student per-skill observation sequences, no cross-skill transfer; compound skill tags remain compound',
        'time_handling': 'chronological per skill by order_id; forgetting per observed skill opportunity, not wall-clock time',
        'selected_model_params': {family: {'slip':v[0], 'guess':v[1], 'learn':v[2], 'forget':v[3]}
                                  for family,v in best_models.items()},
        'split_counts': {s: {'n_students':len(content['students'][s]),
                            'n_events':sum(len(x) for x in content['groups'][s].values())}
                         for s in ('train','development','sealed_test')},
        'skipped_rows_missing_skill': content['skipped_missing_skill'],
        'development_scores': {name: stripped(val) for name,val in scores.items()},
        'paired_brier_differences': {
            'forgetting_minus_no_forgetting': paired_bootstrap(scores['with_forgetting'], scores['no_forgetting'], key=118),
            'forgetting_minus_constant': paired_bootstrap(scores['with_forgetting'], scores['train_prevalence_constant'], key=117),
        },
        'does_not_establish': [
            'Causal recovery-intervention efficacy',
            'Reliable identification of latent forgetting or mastery',
            'Parameter identifiability',
            'Generalization to behavioral-economics curricula',
            'Independent IJCAI algorithmic novelty',
            'Confirmatory generalization to sealed test students',
            'Human study authorization',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Authorized LOCAL CSV path; no download performed')
    parser.add_argument('--output', type=Path, help='Aggregate-only JSON output (optional)')
    args = parser.parse_args()
    result = benchmark(args.input)
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        if args.output.resolve() == args.input.resolve():
            raise ValueError('Cannot overwrite source dataset')
        args.output.write_text(output + '\n', encoding='utf-8')
        print('Aggregate development report saved; no raw student records or student identifiers included.')
    else:
        print(output)

if __name__ == '__main__':
    main()
