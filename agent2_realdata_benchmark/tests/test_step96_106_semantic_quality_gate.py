"""Prove diagnostic detects important defects and never approves draft content."""
import csv
import json
from pathlib import Path
import pytest
from scripts.step96_106_authoring_drafts import CONCEPTS, BLOOM, ACTIONS, FORMS, ITEM_FIELDS, RESOURCE_FIELDS, author, write_rows
from scripts.step96_106_semantic_quality_gate import assess, run, read_csv


def fixture():
    items=[];i=0
    for form in ('pretest','posttest'):
        for concept in CONCEPTS:
            for bloom in (('understand','apply') if form=='pretest' else ('analyze','evaluate')):
                i+=1
                row=dict.fromkeys(ITEM_FIELDS,'');row.update(item_id=f'BE_{form.upper()}_{i:03d}',form=form,concept=concept,bloom=bloom,review_decision='pending');items.append(row)
    for concept in CONCEPTS:
        for bloom in BLOOM:
            i+=1
            row=dict.fromkeys(ITEM_FIELDS,'');row.update(item_id=f'BE_PRACTICE_{i:03d}',form='practice',concept=concept,bloom=bloom,review_decision='pending');items.append(row)
    for concept in CONCEPTS[:7]:
        i+=1
        row=dict.fromkeys(ITEM_FIELDS,'');row.update(item_id=f'BE_PRACTICE_{i:03d}',form='practice',concept=concept,bloom='remember',review_decision='pending');items.append(row)
    for concept in CONCEPTS:
        i+=1
        row=dict.fromkeys(ITEM_FIELDS,'');row.update(item_id=f'BE_DROP_{i:03d}',form='recovery_drop2',concept=concept,bloom='understand',review_decision='pending');items.append(row)
    resources=[]
    for idx,(concept,action) in enumerate(((c,a) for c in CONCEPTS for a in ACTIONS),1):
        row=dict.fromkeys(RESOURCE_FIELDS,'')
        row.update(resource_id=f'BE_R_{idx:03d}',concept=concept,action=action,review_decision='pending')
        resources.append(row)
    return author(items,resources)


def test_complete_fixture_flags_construct_and_parallel_forms():
    items, resources = fixture()
    r=assess(items,resources)
    assert r['item_count']==95 and r['resource_count']==32
    assert r['review_pending_count']==127
    assert r['flag_counts']['unmatched_prepost_bloom_blueprints']==1
    assert r['flag_counts']['unmatched_concept_bloom']==8
    assert r['flag_counts']['create_is_multiple_choice']>=8
    assert not r['human_study_authorized'] and not r['independent_expert_approval_verified']


def test_cross_form_option_leakage_flagged():
    items,resources=fixture()
    a=next(x for x in items if x['form']=='pretest' and x['concept']=='Utility')
    b=next(x for x in items if x['form']=='posttest' and x['concept']=='Utility')
    for k in ('option_A','option_B','option_C','option_D','rationale'):
        b[k]=a[k]
    r=assess(items,resources)
    assert any(x['code']=='shared_choice_set' and set(x['ids'])=={a['item_id'],b['item_id']} for x in r['flags'])
    assert any(x['code']=='shared_prepost_rationale' for x in r['flags'])


def test_exact_duplicate_stems_flagged():
    items,resources=fixture()
    items[1]['prompt']=items[0]['prompt']
    assert 'exact_duplicate_prompt' in assess(items,resources)['flag_counts']


def test_choice_count_and_missing_key_flagged():
    items,resources=fixture()
    items[0]['correct_option_id']='Z'
    items[0]['option_B']=''
    r=assess(items,resources)
    assert 'missing_or_invalid_content' in r['flag_counts']
    assert 'wrong_number_of_choices' in r['flag_counts']


def test_all_read_only_and_hashes_match(tmp_path):
    items,resources=fixture()
    i=tmp_path/'i.csv';r=tmp_path/'r.csv';out=tmp_path/'report.json'
    write_rows(i,ITEM_FIELDS,items);write_rows(r,RESOURCE_FIELDS,resources)
    before=(i.read_bytes(),r.read_bytes())
    report=run(i,r,out)
    assert (i.read_bytes(),r.read_bytes())==before
    assert json.loads(out.read_text())==report
    assert len(report['item_sha256'])==64


def test_fail_closed_wrong_schema(tmp_path):
    x=tmp_path/'bad.csv';x.write_text('abc,def\n1,2\n')
    with pytest.raises(ValueError):read_csv(x,{'concept'})


def test_wrong_count_fails():
    a,b=fixture()
    with pytest.raises(ValueError):assess(a[:-1],b)


def test_duplicate_id_fails():
    a,b=fixture(); a[1]['item_id']=a[0]['item_id']
    with pytest.raises(ValueError,match='Duplicate'):assess(a,b)


def test_overwrite_prevention(tmp_path):
    a,b=fixture()
    i=tmp_path/'i.csv';r=tmp_path/'r.csv'
    write_rows(i,ITEM_FIELDS,a);write_rows(r,RESOURCE_FIELDS,b)
    with pytest.raises(ValueError,match='Refusing to overwrite'):
        run(i,r,i)


def test_similarity_threshold_validation():
    a,b=fixture()
    with pytest.raises(ValueError):assess(a,b,threshold=0.2)


def test_generated_bank_not_falsely_certified():
    a,b=fixture(); report=assess(a,b)
    assert report['status'].startswith('REVIEW REQUIRED')
    assert 'Psychometric' not in report['status']


def test_same_answer_choices_in_practice_and_assessment_is_high_risk():
    items,resources=fixture()
    report=assess(items,resources)
    matching=[e for e in report['flags'] if e['code']=='shared_choice_set' and e['severity']=='high']
    assert matching, 'The representative blueprint must surface assessment/practice reuse'
