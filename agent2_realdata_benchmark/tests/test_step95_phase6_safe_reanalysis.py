"""No real student records. Tests do not change original membership or split."""
import csv
import json
from pathlib import Path
import sys
import types
import pytest
from scripts import step95_phase6_safe_reanalysis as a


def make_fixture(tmp_path):
    root=tmp_path/'frozen'
    root.mkdir()
    members={
        'train':{f'train{n}' for n in range(35)},
        'val':{f'val{n}' for n in range(25)},
        'test':{f'test{n}' for n in range(20)},
    }
    for key, group in members.items():
        (root/f'{key}_students.json').write_text(json.dumps(sorted(group)))
    path=tmp_path/'authorized.csv'
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=['user_id','skill_id','order_id','correct','original'])
        w.writeheader()
        for part, group in members.items():
            for sid in sorted(group):
                for step in range(5):
                    w.writerow(dict(user_id=sid,skill_id='skillA',order_id=step,
                                    correct=int((step+len(sid))%3>0),original=1))
    return root,path,members


def fake_old_module(monkeypatch):
    """Only for testing a standalone local fixture without user's full repo."""
    mod=types.ModuleType('scripts.step95_assistments_realdata_dev')
    mod.stable_split=lambda sid: ('train' if sid.endswith('0') else ('development' if sid.endswith('1') else 'sealed_test'))
    mod.GRIDS={'no_forgetting':((.1,.25,.2,0.),), 'with_forgetting':((.1,.25,.2,.08),)}
    def grouped_scores(groups,model=None,constant=None):
        d={}
        for (student,skill), seq in groups.items():
            p=(constant if model is None else 0.6-model[3])
            row=d.setdefault(student,[0.,0.,0])
            for e in seq:
                row[0]+=(p-int(e.correct))**2
                row[1]+=-(__import__('math').log(p) if e.correct else __import__('math').log(1-p))
                row[2]+=1
        n=sum(x[2] for x in d.values())
        return {'brier':sum(x[0] for x in d.values())/n,
                'log_loss':sum(x[1] for x in d.values())/n,
                'n_students':len(d),'n_observations':n,'_by_student':d}
    def boot(x,y, key):return {'brier_difference':x['brier']-y['brier'],'descriptive_student_cluster_bootstrap_95pct_interval':[0.,0.]}
    mod.grouped_scores=grouped_scores
    mod.paired_bootstrap=boot
    monkeypatch.setitem(sys.modules,'scripts.step95_assistments_realdata_dev',mod)


def test_frozen_partition_counts(tmp_path):
    root,_,m=make_fixture(tmp_path)
    out,meta=a.read_memberships(root)
    assert out==m
    assert meta['phase6_membership_counts']=={'train':35,'val':25,'test':20}
    assert all(len(v)==64 for v in meta['phase6_membership_sha256'].values())


def test_refuse_overlap(tmp_path):
    root,_,m=make_fixture(tmp_path)
    (root/'test_students.json').write_text(json.dumps(sorted(m['test']|{'train1'})))
    with pytest.raises(ValueError,match='overlap'):a.read_memberships(root)


def test_refuse_duplicate_member(tmp_path):
    root,_,m=make_fixture(tmp_path)
    (root/'train_students.json').write_text(json.dumps(['train1','train1']))
    with pytest.raises(ValueError,match='Duplicate'):a.read_memberships(root)


def test_refuse_missing_frozen_file(tmp_path):
    root,_,_=make_fixture(tmp_path)
    (root/'test_students.json').unlink()
    with pytest.raises(ValueError,match='Missing frozen'):a.read_memberships(root)


def test_no_test_labels_even_when_corrupt(tmp_path):
    root,path,m=make_fixture(tmp_path)
    # All original TEST answers are nonsensical; none should be parsed.
    with path.open('a',encoding='utf8') as f:f.write('test0,skillB,999,UNREAD,1\n')
    sequences,meta=a.load_phase6_only(path,m)
    assert meta['phase6_test_labels_evaluated']==0
    assert meta['eligible_student_counts']=={'train':35,'val':25}
    assert all(not sid.startswith('test') for s in sequences.values() for (sid,skill) in s)


def test_fail_closed_unknown_student(tmp_path):
    root,path,m=make_fixture(tmp_path)
    with path.open('a',encoding='utf8') as f:f.write('unknown,skillB,999,1,1\n')
    with pytest.raises(ValueError,match='missing from frozen'):a.load_phase6_only(path,m)


def test_reject_duplicate_events(tmp_path):
    root,path,m=make_fixture(tmp_path)
    with path.open('a',encoding='utf8') as f:f.write('val0,skillA,1,1,1\n')
    with pytest.raises(ValueError,match='Repeated'):a.load_phase6_only(path,m)


def test_non_original_skipped(tmp_path):
    root,path,m=make_fixture(tmp_path)
    with path.open('a',encoding='utf8') as f:f.write('val0,skillA,999,0,0\n')
    _,meta=a.load_phase6_only(path,m)
    assert meta['row_counts']['val_nonoriginal_excluded']==1
    assert meta['row_counts']['val_eligible_rows']==125


def test_stable_census_no_ids_exposed(monkeypatch,tmp_path):
    fake_old_module(monkeypatch)
    _,_,m=make_fixture(tmp_path)
    census=a.overlap_census(m)
    assert census['test']['train']>0
    assert 'test0' not in json.dumps(census)


def test_report_excludes_private_identifiers(monkeypatch,tmp_path):
    fake_old_module(monkeypatch)
    root,path,_=make_fixture(tmp_path)
    report=a.run(path,root)
    assert report['original_phase6_test_outcomes_used_in_this_run'] is False
    assert report['human_study_authorized'] is False
    assert report['causal_recovery_effect_established'] is False
    assert report['can_certify_clean_independent_heldout_generalization'] is False
    assert report['models_selected_on_phase6_train_only'] is True
    text=json.dumps(report)
    for sid in ('train0','val0','test0'):
        assert sid not in text


def test_expected_grid_used_without_sealed_labels(monkeypatch,tmp_path):
    fake_old_module(monkeypatch)
    root,path,_=make_fixture(tmp_path)
    r=a.run(path,root)
    assert len(r['phase6_val_metrics'])==5
    assert r['eligible_student_counts']=={'train':35,'val':25}
    assert set(r['different_split_overlap_counts'])==set(a.SPLIT_NAMES)


def test_no_data_modification(monkeypatch,tmp_path):
    fake_old_module(monkeypatch)
    root,path,_=make_fixture(tmp_path)
    data_hash=a.sha_file(path)
    split_hash=a.sha_file(root/'test_students.json')
    a.run(path,root)
    assert a.sha_file(path)==data_hash
    assert a.sha_file(root/'test_students.json')==split_hash
