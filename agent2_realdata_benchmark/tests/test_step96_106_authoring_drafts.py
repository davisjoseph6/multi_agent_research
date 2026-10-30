"""Draft-authoring safety tests; review approvals must never be forged."""
import csv
import json
from pathlib import Path
import pytest

from scripts.step96_106_authoring_drafts import (
    C, CONCEPTS, BLOOM, ACTIONS, FORMS, ITEM_FIELDS, RESOURCE_FIELDS,
    author, load_rows, run, write_rows,
)


def fixture_rows():
    items=[]; i=0
    for form in ('pretest','posttest'):
        for concept in CONCEPTS:
            for bloom in (('understand','apply') if form=='pretest' else ('analyze','evaluate')):
                i+=1;items.append(dict.fromkeys(ITEM_FIELDS,''))
                items[-1].update(item_id=f'BE_{form.upper()}_{i:03d}',form=form,concept=concept,bloom=bloom,review_decision='pending')
    for concept in CONCEPTS:
        for bloom in BLOOM:
            i+=1;items.append(dict.fromkeys(ITEM_FIELDS,''))
            items[-1].update(item_id=f'BE_PRACTICE_{i:03d}',form='practice',concept=concept,bloom=bloom,review_decision='pending')
    for concept in CONCEPTS[:7]:
        i+=1;items.append(dict.fromkeys(ITEM_FIELDS,''))
        items[-1].update(item_id=f'BE_PRACTICE_{i:03d}',form='practice',concept=concept,bloom='remember',review_decision='pending')
    for concept in CONCEPTS:
        i+=1;items.append(dict.fromkeys(ITEM_FIELDS,''))
        items[-1].update(item_id=f'BE_DROP_{i:03d}',form='recovery_drop2',concept=concept,bloom='understand',review_decision='pending')
    resources=[];j=0
    for concept in CONCEPTS:
        for action in ACTIONS:
            j+=1;resources.append(dict.fromkeys(RESOURCE_FIELDS,''))
            resources[-1].update(resource_id=f'BE_R_{j:03d}',concept=concept,action=action,review_decision='pending')
    assert len(items)==95 and len(resources)==32
    return items,resources


def test_complete_catalog():
    assert set(C)==set(CONCEPTS)
    assert all(set(C[concept])==set(BLOOM) for concept in CONCEPTS)


def test_all_catalog_answers_distinct():
    for concept in CONCEPTS:
        for bloom in BLOOM:
            first,second,correct,*tail=C[concept][bloom]
            assert first != second
            assert all(x.strip() for x in (first,second,correct,*tail))
            assert len(set((correct,*tail[:3])))==4


def test_95_32_rows_preserved_and_unreviewed():
    rows,res=fixture_rows()
    authored,resources=author(rows,res)
    assert len(authored)==95 and len(resources)==32
    assert [r['item_id'] for r in authored]==[r['item_id'] for r in rows]
    assert [r['resource_id'] for r in resources]==[r['resource_id'] for r in res]
    assert all(r['review_decision']=='pending' and not r['reviewer_record'] and not r['review_date'] for r in authored+resources)
    assert all(r['prompt'] and r['rationale'] and r['source_citation'] for r in authored)
    assert all(r['resource_text'] and r['source_citation'] for r in resources)


def test_options_and_keys_well_formed():
    authored,_=author(*fixture_rows())
    for r in authored:
        available=[k for k in 'ABCD' if r['option_'+k]]
        assert r['correct_option_id'] in available
        assert len(available)==(2 if r['form']=='recovery_drop2' else 4)
        assert len(set(r['option_'+k] for k in available))==len(available)


def test_no_duplicate_prompt_even_with_reused_concept_bloom():
    authored,_=author(*fixture_rows())
    prompts=[r['prompt'].casefold().strip() for r in authored]
    assert len(prompts)==len(set(prompts))


def test_review_ledger_and_manifest(tmp_path):
    source_i=tmp_path/'i.csv';source_r=tmp_path/'r.csv';target=tmp_path/'draft'
    items,resources=fixture_rows()
    write_rows(source_i,ITEM_FIELDS,items);write_rows(source_r,RESOURCE_FIELDS,resources)
    m=run(source_i,source_r,target)
    assert m['reviewed_count']==0 and m['authorized_for_human_study'] is False
    with (target/'review_ledger_PENDING.csv').open(newline='') as s:
        review=list(csv.DictReader(s))
    assert len(review)==127
    assert {r['decision'] for r in review}=={'pending'}
    assert json.loads((target/'manifest.json').read_text())==m


def test_no_overwrite_of_prior_review_draft(tmp_path):
    items,resources=fixture_rows()
    i=tmp_path/'i.csv';r=tmp_path/'r.csv';output=tmp_path/'draft'
    write_rows(i,ITEM_FIELDS,items);write_rows(r,RESOURCE_FIELDS,resources)
    run(i,r,output)
    with pytest.raises(FileExistsError):run(i,r,output)


def test_reject_previously_authored_slot():
    i,r=fixture_rows();i[0]['prompt']='Already authored by researcher'
    with pytest.raises(ValueError,match='refuse to overwrite'):author(i,r)


def test_reject_previously_reviewed_slot():
    i,r=fixture_rows();r[0]['review_date']='2026-10-30'
    with pytest.raises(ValueError,match='refuse to overwrite'):author(i,r)


def test_reject_missing_content_slot():
    i,r=fixture_rows();i.pop()
    with pytest.raises(ValueError):author(i,r)


def test_reject_duplicate_ids():
    i,r=fixture_rows();i[0]['item_id']=i[1]['item_id']
    with pytest.raises(ValueError):author(i,r)


def test_reject_resource_grid_gap():
    i,r=fixture_rows();r[0]['action']='INVALID'
    with pytest.raises(ValueError):author(i,r)


def test_review_record_not_synthetic_validation(tmp_path):
    i,r=fixture_rows();ip=tmp_path/'input_items.csv';rp=tmp_path/'input_resources.csv'
    write_rows(ip,ITEM_FIELDS,i);write_rows(rp,RESOURCE_FIELDS,r)
    m=run(ip,rp,tmp_path/'output')
    assert m['empirical_difficulty_estimated'] is False
    assert m['free_response_create_competency_validated'] is False


def test_wrong_schema_rejected(tmp_path):
    p=tmp_path/'bad.csv';p.write_text('id,wrong\n1,bad\n')
    with pytest.raises(ValueError,match='Unexpected schema'):load_rows(p,ITEM_FIELDS)
