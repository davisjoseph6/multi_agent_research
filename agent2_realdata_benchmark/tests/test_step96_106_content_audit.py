"""Development-only structural tests for content release gate."""
import csv
from pathlib import Path

from scripts.step96_106_content_audit import (
    CONCEPTS, BLOOM, FORMS, ACTIONS, read_csv,
    audit_items, audit_resources,
)

ROOT = Path(__file__).parents[1]


def items():
    return read_csv(ROOT/'docs/step96_106_authorship_slots.csv')


def resources():
    return read_csv(ROOT/'docs/step104_recovery_resource_slots.csv')


def test_authorship_blueprint_contains_all_95_slots():
    rows = items()
    assert len(rows) == 95
    assert {k: sum(r['form'] == k for r in rows) for k in FORMS} == FORMS


def test_practice_blueprint_covers_all_concept_bloom_pairs():
    rows = items()
    pairs = {(r['concept'],r['bloom']) for r in rows if r['form']=='practice'}
    assert pairs == {(c,b) for c in CONCEPTS for b in BLOOM}


def test_parallel_form_blueprint_concept_balance():
    rows = items()
    for form in ('pretest','posttest'):
        assert {c: sum(r['form']==form and r['concept']==c for r in rows) for c in CONCEPTS} == dict.fromkeys(CONCEPTS,2)


def test_recovery_resources_cover_8_by_4():
    rows = resources()
    assert len(rows) == 32
    assert {(r['concept'],r['action']) for r in rows} == {(c,a) for c in CONCEPTS for a in ACTIONS}


def test_draft_items_fail_closed_without_real_questions_and_review():
    errs = audit_items(items())
    assert errs
    assert any('review is not approved' in e for e in errs)
    assert any('prompt is blank' in e for e in errs)


def test_draft_resources_fail_closed_without_content_and_review():
    errs = audit_resources(resources())
    assert errs
    assert any('resource_text' in e for e in errs)


def test_duplicate_prompt_is_rejected():
    rows = items()
    rows[0]['prompt'] = 'Duplicated question?'
    rows[1]['prompt'] = ' Duplicated   question? '
    assert any('duplicate prompt' in e for e in audit_items(rows))


def test_synthetic_options_are_rejected():
    rows = items()
    rows[0]['option_A'] = 'Synthetic option A'
    assert any('synthetic fixture' in e for e in audit_items(rows))


def test_review_flag_without_external_record_is_rejected():
    rows = resources()
    rows[0]['review_decision'] = 'approved'
    assert any('missing independent review record' in e for e in audit_resources(rows))


def test_closure_register_has_52_rows_and_55_8_percent_proxy():
    import csv
    from scripts.step72_123_progress import summarize
    with (ROOT/'docs/steps72_123_closure_register.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    result = summarize(rows)
    assert result['provisional_percentage'] == 55.8
    assert result['status_counts']['SYNTHETIC-IMPLEMENTED'] == 19
    assert result['status_counts']['PARTIAL'] == 20
    assert result['status_counts']['EXTERNAL-REQUIRED'] == 13
    assert result['human_study_authorized'] is False


def test_invalid_closure_credit_is_not_accepted():
    import csv
    import pytest
    from scripts.step72_123_progress import summarize
    with (ROOT/'docs/steps72_123_closure_register.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    rows[0]['evidence_credit'] = '1.0'
    with pytest.raises(ValueError, match='credit'):
        summarize(rows)
