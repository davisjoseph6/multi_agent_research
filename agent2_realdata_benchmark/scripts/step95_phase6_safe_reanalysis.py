"""Read-only Phase 6 student-partition-safe Step 95 real-data DEVELOPMENT audit.

Uses ONLY original frozen Phase 6 TRAIN students to select model settings and
ONLY original Phase 6 VAL students for exploratory prequential metrics.
Phase 6 TEST student responses are deliberately not parsed or scored.

No learner identifiers / individual responses are written to the report.
No original split, data, or benchmark source files are modified.
NO confirmatory claim, treatment-efficacy claim, or held-out test evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

SPLIT_NAMES = ("train", "val", "test")
EXPECTED_ROWS = ("user_id", "skill_id", "order_id", "correct")


def sha_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as fd:
        for block in iter(lambda: fd.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read_memberships(folder: Path) -> tuple[dict[str, set[str]], dict]:
    """Verify every Phase 6 membership file independently, no silent repair."""
    partitions = {}
    hashes = {}
    for name in SPLIT_NAMES:
        path = folder / f"{name}_students.json"
        if not path.is_file():
            raise ValueError(f"Missing frozen Phase 6 student membership: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or any(not isinstance(x, (str, int)) or isinstance(x, bool) or not str(x).strip() for x in raw):
            raise ValueError(f"Invalid Phase 6 {name} membership representation")
        values = [str(x) for x in raw]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate student membership within Phase 6 {name}")
        partitions[name] = set(values)
        hashes[name] = sha_file(path)
    for i, name in enumerate(SPLIT_NAMES):
        for other in SPLIT_NAMES[i+1:]:
            if partitions[name] & partitions[other]:
                raise ValueError("Frozen Phase 6 student partitions overlap: fail closed")
    if not all(partitions.values()):
        raise ValueError("All three frozen Phase 6 partitions must be nonempty")
    return partitions, {"phase6_membership_sha256": hashes,
                        "phase6_membership_counts": {k: len(v) for k, v in partitions.items()}}


def overlap_census(memberships: Mapping[str, set[str]]) -> dict:
    """Compare original Phase 6 membership with newer Step 95 hash, IDs never output."""
    # Import the actual committed function, so the audit cannot drift from it.
    from scripts.step95_assistments_realdata_dev import stable_split
    table = {}
    for phase6_name in SPLIT_NAMES:
        cross = Counter(stable_split(sid) for sid in memberships[phase6_name])
        table[phase6_name] = {key: cross[key] for key in ("train", "development", "sealed_test")}
    return table


@dataclass(frozen=True)
class Observation:
    order: int
    correct: bool


def load_phase6_only(path: Path, memberships: Mapping[str, set[str]], *, min_students: int = 10) -> tuple[dict, dict]:
    """Parse response labels only AFTER verifying membership is train or val.

    Every incoming line is inevitably decoded by CSV reader; "no test labels
    evaluated" is accurate, whereas "never read file bytes" is not.
    """
    if not path.is_file() or path.suffix.lower() != '.csv':
        raise ValueError(f"Input must be an existing, locally authorized CSV: {path}")
    owners = {sid: name for name, population in memberships.items() for sid in population}
    sequences = {"train": defaultdict(list), "val": defaultdict(list)}
    students = {"train": set(), "val": set()}
    duplicate_keys = set()
    stats = Counter()
    with path.open(encoding="utf-8-sig", errors="strict", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(EXPECTED_ROWS).issubset(reader.fieldnames):
            raise ValueError("CSV must have user_id, skill_id, order_id, correct")
        for line_number, row in enumerate(reader, 2):
            stats['all_csv_rows'] += 1
            sid = (row.get('user_id') or '').strip()
            if not sid:
                raise ValueError(f"Missing student ID in input CSV line {line_number}")
            partition = owners.get(sid)
            if partition is None:
                raise ValueError(f"CSV contains student missing from frozen Phase 6 membership (row {line_number})")
            if partition == 'test':
                stats['phase6_test_rows_excluded_before_outcome_parsing'] += 1
                continue
            if 'original' in row and (row.get('original') or '').strip() not in ('1', '1.0', ''):
                stats[f'{partition}_nonoriginal_excluded'] += 1
                continue
            skill = (row.get('skill_id') or '').strip()
            if not skill or skill.lower() in ('nan', 'null', 'none'):
                stats[f'{partition}_missing_skill_excluded'] += 1
                continue
            answer = (row.get('correct') or '').strip()
            if answer not in ('0', '1', '0.0', '1.0'):
                raise ValueError(f"Non-binary response in {partition} CSV line {line_number}")
            raw_order = (row.get('order_id') or '').strip()
            try:
                if not raw_order or raw_order != str(int(raw_order)):
                    raise ValueError('Not a normalized integer')
                order = int(raw_order)
            except ValueError as exc:
                raise ValueError(f"Invalid event order in {partition} CSV line {line_number}") from exc
            event_key = (sid, skill, order)
            if event_key in duplicate_keys:
                raise ValueError(f"Repeated student-skill-order in {partition}: use deduplicated corrected release")
            duplicate_keys.add(event_key)
            sequences[partition][(sid, skill)].append(Observation(order, answer in ('1', '1.0')))
            students[partition].add(sid)
            stats[f'{partition}_eligible_rows'] += 1
    for name in ('train', 'val'):
        if len(students[name]) < min_students:
            raise ValueError(f"Not enough {name} students with eligible interactions ({len(students[name])})")
        for series in sequences[name].values():
            series.sort(key=lambda x: x.order)
    return sequences, {"row_counts": dict(stats),
                       "eligible_student_counts": {name: len(s) for name, s in students.items()},
                       "membership_exclusion_asserted": True,
                       "phase6_test_labels_evaluated": 0}


def score_report(sequences: Mapping[str, dict]) -> dict:
    from scripts.step95_assistments_realdata_dev import GRIDS, grouped_scores, paired_bootstrap
    train = sequences['train']
    val = sequences['val']
    total = sum(len(v) for v in train.values())
    if not total:
        raise ValueError('No eligible training observations')
    correct = sum(sum(e.correct for e in obs) for obs in train.values())
    prevalence = max(1e-6, min(1-1e-6, correct/total))
    chosen = {}
    train_selection_loss = {}
    for family, candidates in GRIDS.items():
        # Model selected on original Phase 6 TRAIN only. No validation labels.
        candidate = min((grouped_scores(train, model=m)['log_loss'], m) for m in candidates)
        train_selection_loss[family], chosen[family] = candidate
    # Explicit fixed non-forgetting params, exploratory sensitivity based on
    # prior reported development configurations; not a preregistered test.
    fixed = (0.1, 0.25, 0.2, 0.0)
    matched = (0.1, 0.25, 0.2, 0.08)
    all_scores = {
        "constant_training_prevalence": grouped_scores(val, None, prevalence),
        "train_selected_no_forgetting": grouped_scores(val, chosen['no_forgetting']),
        "train_selected_with_forgetting": grouped_scores(val, chosen['with_forgetting']),
        "fixed_params_no_forgetting": grouped_scores(val, fixed),
        "matched_params_with_forgetting": grouped_scores(val, matched),
    }
    # `_by_student` contains identifiers: keep ONLY internal in-memory.
    public_scores = {key: {k: v for k, v in s.items() if not k.startswith('_')}
                     for key, s in all_scores.items()}
    contrasts = {
        'train_selected_forgetting_minus_no_forgetting': paired_bootstrap(
            all_scores['train_selected_with_forgetting'], all_scores['train_selected_no_forgetting'], key=2211),
        'fixed_matched_forgetting_minus_no_forgetting': paired_bootstrap(
            all_scores['matched_params_with_forgetting'], all_scores['fixed_params_no_forgetting'], key=2212),
        'train_selected_forgetting_minus_constant': paired_bootstrap(
            all_scores['train_selected_with_forgetting'], all_scores['constant_training_prevalence'], key=2213),
    }
    return {"models_selected_on_phase6_train_only": True,
            "selected_parameters": {k: dict(zip(('slip','guess','learn','forget'), v)) for k,v in chosen.items()},
            "train_selection_log_loss": train_selection_loss,
            "fixed_matched_sensitivity_parameters": {
                "no_forgetting": list(fixed), "with_forgetting": list(matched)},
            "phase6_val_metrics": public_scores,
            "descriptive_paired_student_bootstrap": contrasts}


def run(data_path: Path, membership_folder: Path, *, min_students: int = 10) -> dict:
    members, manifest = read_memberships(membership_folder)
    cross = overlap_census(members)
    series, observations = load_phase6_only(data_path, members, min_students=min_students)
    analysis = score_report(series)
    return {
        "status": "POST-HOC EXPLORATORY DEVELOPMENT: NOT A CONFIRMATORY TEST",
        "input_csv_sha256": sha_file(data_path),
        **manifest,
        "different_split_overlap_counts": cross,
        "original_phase6_test_overlap_with_new_step95_train": cross['test']['train'],
        "original_phase6_test_overlap_with_new_step95_development": cross['test']['development'],
        "separation":"Only original Phase 6 TRAIN responses fit models; only original Phase 6 VAL responses scored. TEST outcomes excluded before parsing.",
        "original_phase6_test_outcomes_used_in_this_run": False,
        "existing_new_step95_run_exposed_phase6_test_students": True,
        "locked_phase6_validation_is_previously_used_for_research_selection": True,
        **observations,
        **analysis,
        "human_study_authorized": False,
        "causal_recovery_effect_established": False,
        "real_forgetting_events_observed": False,
        "can_certify_clean_independent_heldout_generalization": False,
        "limitations": [
            "Original Phase 6 test membership overlapped the earlier separate Step 95 exploratory split: cannot retroactively claim independence for that analysis.",
            "This re-analysis avoids original test outcomes, but original Phase 6 validation has previously guided project development; interpret as exploratory.",
            "The same public dataset and student population have been used repeatedly; a genuinely independent confirmation needs a separate untouched protocol/data source.",
            "Prediction of correctness on ASSISTments mathematics is not latent forgetting identification or an intervention-effect estimate.",
            "Model parameters and split-specific performance do not establish transfer to Behavioral Economics learners.",
            "Missing independent assessment, ethics/privacy and scientific reviews remain outstanding."
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='LOCAL private corrected UTF-8 CSV')
    parser.add_argument('--splits', required=True, type=Path, help='Original data/splits/assist2009 directory')
    parser.add_argument('--output', required=True, type=Path, help='Aggregate-only JSON location outside Git')
    args = parser.parse_args()
    protected = {args.input.resolve()} | {(args.splits / f'{name}_students.json').resolve() for name in SPLIT_NAMES}
    if args.output.resolve() in protected:
        parser.error('Output must not overwrite source data or frozen membership files')
    if not args.output.resolve().is_relative_to(Path('/tmp').resolve()):
        parser.error('Privacy safeguard: write aggregate evidence only under /tmp, outside the repository')
    if args.output.exists():
        parser.error('Refusing to overwrite preexisting aggregate analysis (version results instead)')
    if args.output.suffix != '.json':
        parser.error('Output must be a .json report')
    report = run(args.input, args.splits)
    # Do not leak identifiers even via exception repr/report internals.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write('\n')
    print('Phase 6 TRAIN/VAL-only aggregate report written. Original TEST labels not scored.')
    print('TRAIN students:', report['eligible_student_counts']['train'])
    print('VAL students:', report['eligible_student_counts']['val'])
    print('Earlier Step 95 use of Phase 6 TEST membership: training', report['original_phase6_test_overlap_with_new_step95_train'],
          ', development', report['original_phase6_test_overlap_with_new_step95_development'])
    for model, metrics in report['phase6_val_metrics'].items():
        print(model, 'Brier:', round(metrics['brier'], 6), 'log-loss:', round(metrics['log_loss'], 6))
    print('Post-hoc exploratory only. No participant or held-out-test causal claims.')


if __name__ == '__main__':
    main()
