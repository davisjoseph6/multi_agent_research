"""Substantive assessment-form revision safeguards, not human item validity."""
import csv
import json
from pathlib import Path
import pytest

from scripts.step96_106_authoring_drafts import (
    CONCEPTS, BLOOM, ACTIONS, ITEM_FIELDS, RESOURCE_FIELDS, author, write_rows,
)
from scripts.step96_106_semantic_quality_gate import assess
from scripts.step96_106_revise_parallel_forms import PAIRS, revise, run, digest


def source_fixture():
    items=[]
    for form in ('pretest','posttest'):
        for ci, concept in enumerate(CONCEPTS):
            for j,bloom in enumerate(('understand','apply')):
                row=dict.fromkeys(ITEM_FIELDS,'')
                row.update(item_id=f'BE_{form.upper()}_{ci*2+j+1:03d}',
                           form=form,concept=concept,bloom=bloom,review_decision='pending')
                items.append(row)
    counter=0
    for concept in CONCEPTS:
        for bloom in BLOOM:
            counter+=1
            row=dict.fromkeys(ITEM_FIELDS,'')
            row.update(item_id=f'BE_PRACTICE_{counter:03d}',form='practice',
                       concept=concept,bloom=bloom,review_decision='pending')
            items.append(row)
    for concept in CONCEPTS[:7]:
        counter+=1
        row=dict.fromkeys(ITEM_FIELDS,'')
        row.update(item_id=f'BE_PRACTICE_{counter:03d}',form='practice',
                   concept=concept,bloom='remember',review_decision='pending')
        items.append(row)
    for ci, concept in enumerate(CONCEPTS):
        row=dict.fromkeys(ITEM_FIELDS,'')
        row.update(item_id=f'BE_DROP_{ci+1:03d}',form='recovery_drop2',
                   concept=concept,bloom='apply',review_decision='pending')
        items.append(row)
    resources=[]
    for idx,(concept,action) in enumerate((c,a) for c in CONCEPTS for a in ACTIONS):
        row=dict.fromkeys(RESOURCE_FIELDS,'')
        row.update(resource_id=f'BE_R_{idx+1:03d}',concept=concept,action=action,review_decision='pending')
        resources.append(row)
    return author(items,resources)


def test_complete_bank_and_editorial_entries():
    assert len(PAIRS)==8
    assert all(set(PAIRS[c])=={'understand','apply'} for c in CONCEPTS)
    assert all(set(PAIRS[c][b])=={'pretest','posttest'} for c in CONCEPTS for b in ('understand','apply'))
    for c in CONCEPTS:
        for b in ('understand','apply'):
            for form in ('pretest','posttest'):
                entry=PAIRS[c][b][form]
                assert len(entry)==6 and all(isinstance(s,str) and s.strip() for s in entry)
                assert len({s.casefold() for s in entry[1:5]})==4


def test_substantive_rewrite_reduces_high_risks():
    items,resources=source_fixture()
    before=assess(items,resources)
    new,ids=revise(items)
    after=assess(new,resources)
    assert len(ids)==32
    assert after['severity_counts'].get('high',0)<before['severity_counts'].get('high',0)
    assert after['review_pending_count']==127
    assert after['severity_counts'].get('blocking',0)==0
    assert after['flag_counts'].get('shared_prepost_rationale',0)==0
    assert after['flag_counts'].get('shared_choice_set',0)==0
    assert after['flag_counts'].get('create_is_multiple_choice',0)==8


def test_practice_and_recovery_items_unchanged():
    rows,_=source_fixture()
    after,_=revise(rows)
    for old,new in zip(rows,after):
        if old['form'] not in ('pretest','posttest'):
            assert new==old


def test_identifiers_keys_and_metadata_preserved():
    rows,_=source_fixture()
    after,_=revise(rows)
    for old,new in zip(rows,after):
        assert new['item_id']==old['item_id']
        assert new['correct_option_id']==old['correct_option_id']
        assert new['source_citation']==old['source_citation']
        assert new['review_decision']=='pending'
        assert new['reviewer_record']==new['review_date']==''


def test_prepost_stems_and_options_not_identical():
    old,_=source_fixture()
    after,_=revise(old)
    for c in CONCEPTS:
        for b in ('understand','apply'):
            pre=next(x for x in after if (x['concept'],x['bloom'],x['form'])==(c,b,'pretest'))
            post=next(x for x in after if (x['concept'],x['bloom'],x['form'])==(c,b,'posttest'))
            assert pre['prompt']!=post['prompt']
            assert pre['rationale']!=post['rationale']
            assert {pre['option_'+k] for k in 'ABCD'}!={post['option_'+k] for k in 'ABCD'}


def test_reject_external_approved_record():
    rows,_=source_fixture()
    rows[0]['review_decision']='approved'
    with pytest.raises(ValueError,match='reviewed'):
        revise(rows)


def test_reject_wrong_bloom_blueprint():
    rows,_=source_fixture()
    rows[0]['bloom']='analyze'
    with pytest.raises(ValueError,match='blueprint'):
        revise(rows)


def test_reject_duplicate_id():
    rows,_=source_fixture()
    rows[0]['item_id']=rows[1]['item_id']
    with pytest.raises(ValueError,match='duplicate'):
        revise(rows)


def test_write_new_directory_and_manifest(tmp_path):
    items,resources=source_fixture()
    sourcei=tmp_path/'i.csv'; sourcer=tmp_path/'r.csv'
    write_rows(sourcei,ITEM_FIELDS,items);write_rows(sourcer,RESOURCE_FIELDS,resources)
    sourcei_bytes, sourcer_bytes=sourcei.read_bytes(),sourcer.read_bytes()
    dest=tmp_path/'version2'
    output=run(sourcei,sourcer,dest,expected_item_sha256=digest(sourcei),expected_resource_sha256=digest(sourcer))
    assert sourcei.read_bytes()==sourcei_bytes and sourcer.read_bytes()==sourcer_bytes
    assert output['revised_count']==32
    assert output['review_pending_count']==127
    assert output['unchanged_resource_bytes'] is True
    assert json.loads((dest/'manifest.json').read_text())==output
    with (dest/'authored_items_PENDING_REVIEW.csv').open(newline='',encoding='utf8') as f:
        assert len(list(csv.DictReader(f)))==95


def test_refuse_overwrite_and_unknown_input(tmp_path):
    items,resources=source_fixture()
    sourcei=tmp_path/'i.csv'; sourcer=tmp_path/'r.csv'
    write_rows(sourcei,ITEM_FIELDS,items);write_rows(sourcer,RESOURCE_FIELDS,resources)
    dest=tmp_path/'revision'
    with pytest.raises(ValueError,match='hashes differ'):
        run(sourcei,sourcer,dest)
    assert not dest.exists()
    run(sourcei,sourcer,dest,expected_item_sha256=digest(sourcei),expected_resource_sha256=digest(sourcer))
    with pytest.raises(FileExistsError):
        run(sourcei,sourcer,dest,expected_item_sha256=digest(sourcei),expected_resource_sha256=digest(sourcer))


def test_existing_difficulty_estimates_remain_unmeasured():
    rows,_=source_fixture()
    after,_=revise(rows)
    for a,b in zip(rows,after):
        assert a['difficulty_estimate']==b['difficulty_estimate']


def test_stable_deterministic_revision():
    rows,_=source_fixture()
    a,_=revise(rows); b,_=revise(rows)
    assert a==b
