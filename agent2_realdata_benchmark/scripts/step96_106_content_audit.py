"""Fail-closed structural checks for non-synthetic educational materials.

Passing this checker is NOT expert review, psychometric validation, consent,
or human-study authorization. It checks authored CSV structure only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import json
from pathlib import Path

CONCEPTS = (
    'Utility', 'Loss Aversion', 'Anchoring', 'Sunk Cost',
    'Framing', 'Heuristics', 'Prospect Theory', 'Nudge Theory',
)
BLOOM = ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')
ACTIONS = ('CONCEPT_SUMMARY', 'DROP_2', 'WORKED_EXAMPLE', 'SOCRATIC_HINT')
FORMS = {'pretest': 16, 'posttest': 16, 'practice': 55, 'recovery_drop2': 8}
OPTIONS = ('option_A', 'option_B', 'option_C', 'option_D')
REQUIRED_ITEM_FIELDS = ('learning_objective', 'prompt', 'rationale', 'source_citation')
REQUIRED_RESOURCE_FIELDS = ('learning_objective', 'resource_text', 'source_citation')


def read_csv(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f'No CSV header: {path}')
        return list(reader)


def _review(row, label, issues):
    if row.get('review_decision', '').strip() != 'approved':
        issues.append(f'{label}: review is not approved')
    if not row.get('reviewer_record', '').strip():
        issues.append(f'{label}: missing independent review record reference')
    value = row.get('review_date', '').strip()
    try:
        if not value or date.fromisoformat(value) > date.today():
            raise ValueError
    except ValueError:
        issues.append(f'{label}: review_date must be a real YYYY-MM-DD not in the future')


def audit_items(rows):
    issues = []
    counts = Counter(row.get('form', '') for row in rows)
    for form, target in FORMS.items():
        if counts[form] != target:
            issues.append(f'{form}: expected {target} items, found {counts[form]}')
    if len(rows) != sum(FORMS.values()):
        issues.append('Expected exactly 95 distinct item rows')
    seen_ids, seen_prompts = set(), set()
    covered_practice = set()
    concepts_by_form = {form: Counter() for form in FORMS}
    for i, row in enumerate(rows, 2):
        label = f'item row {i} ({row.get("item_id", "missing ID")})'
        item_id = row.get('item_id', '').strip()
        if not item_id or item_id in seen_ids:
            issues.append(f'{label}: empty or repeated item ID')
        seen_ids.add(item_id)
        form, concept, bloom = (row.get(k, '').strip() for k in ('form', 'concept', 'bloom'))
        if form not in FORMS or concept not in CONCEPTS or bloom not in BLOOM:
            issues.append(f'{label}: unsupported form, concept, or Bloom level')
        else:
            concepts_by_form[form][concept] += 1
            if form == 'practice':
                covered_practice.add((concept, bloom))
        for field in REQUIRED_ITEM_FIELDS:
            if not row.get(field, '').strip():
                issues.append(f'{label}: {field} is blank')
        prompt = ' '.join(row.get('prompt', '').casefold().split())
        if prompt:
            if prompt in seen_prompts:
                issues.append(f'{label}: duplicate prompt across assessment/practice forms')
            seen_prompts.add(prompt)
        text = ' '.join(row.get(key, '') for key in (*REQUIRED_ITEM_FIELDS, *OPTIONS))
        if 'synthetic only' in text.casefold() or 'synthetic option' in text.casefold():
            issues.append(f'{label}: synthetic fixture text is not permitted')
        available = [key[-1] for key in OPTIONS if row.get(key, '').strip()]
        if form == 'recovery_drop2':
            if len(available) != 2:
                issues.append(f'{label}: DROP_2 must contain exactly two distractor/answer options')
        elif len(available) != 4:
            issues.append(f'{label}: expected four response options')
        if row.get('correct_option_id', '').strip() not in available:
            issues.append(f'{label}: no valid correct-option key')
        normalized_choices = [row.get('option_' + letter, '').casefold().strip() for letter in available]
        if len(normalized_choices) != len(set(normalized_choices)):
            issues.append(f'{label}: repeated option text')
        try:
            d = float(row.get('difficulty_estimate', ''))
            if not 0 <= d <= 1:
                raise ValueError
        except (ValueError, TypeError):
            issues.append(f'{label}: difficulty_estimate must be between 0 and 1')
        _review(row, label, issues)
    for form in ('pretest', 'posttest'):
        for concept in CONCEPTS:
            if concepts_by_form[form][concept] != 2:
                issues.append(f'{form}: concept {concept} requires exactly two items')
    if covered_practice != {(c, b) for c in CONCEPTS for b in BLOOM}:
        issues.append('practice: not all 8 x 6 concept/Bloom cells are covered')
    if concepts_by_form['recovery_drop2'] != Counter({c: 1 for c in CONCEPTS}):
        issues.append('recovery_drop2: exactly one item per concept required')
    return issues


def audit_resources(rows):
    issues = []
    seen, coverage = set(), set()
    if len(rows) != 32:
        issues.append(f'Expected 32 recovery resource records, found {len(rows)}')
    for i, row in enumerate(rows, 2):
        label = f'resource row {i} ({row.get("resource_id", "missing ID")})'
        resource_id = row.get('resource_id', '').strip()
        if not resource_id or resource_id in seen:
            issues.append(f'{label}: empty or duplicate resource ID')
        seen.add(resource_id)
        pair = (row.get('concept', '').strip(), row.get('action', '').strip())
        if pair not in {(c, a) for c in CONCEPTS for a in ACTIONS}:
            issues.append(f'{label}: unknown concept/recovery action')
        if pair in coverage:
            issues.append(f'{label}: duplicate concept/action pair')
        coverage.add(pair)
        for field in REQUIRED_RESOURCE_FIELDS:
            if not row.get(field, '').strip():
                issues.append(f'{label}: missing {field}')
        _review(row, label, issues)
    if coverage != {(c, a) for c in CONCEPTS for a in ACTIONS}:
        issues.append('Recovery resource grid must cover all 8 concepts x 4 actions')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items', type=Path, default=Path('docs/step96_106_authorship_slots.csv'))
    parser.add_argument('--resources', type=Path, default=Path('docs/step104_recovery_resource_slots.csv'))
    args = parser.parse_args()
    try:
        items = read_csv(args.items)
        resources = read_csv(args.resources)
        issues = audit_items(items) + audit_resources(resources)
    except (OSError, ValueError) as exc:
        issues = [str(exc)]
    result = {
        'structural_check_passed': not issues,
        'issue_count': len(issues),
        'first_issues': issues[:15],
        'expert_review_verified': False,
        'psychometric_validation_verified': False,
        'authorized_for_human_study': False,
        'interpretation': ('AUTHORED-CONTENT STRUCTURE ONLY' if not issues else 'DRAFT CONTENT: NOT RELEASE READY'),
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if issues else 0)


if __name__ == '__main__':
    main()
