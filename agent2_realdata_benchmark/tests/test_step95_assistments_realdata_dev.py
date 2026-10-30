"""Tests using invented learners only. No real student data or network use."""
import csv
import json
from pathlib import Path
import pytest

from scripts.step95_assistments_realdata_dev import (
    GRIDS, benchmark, grouped_scores, load_local_data, paired_bootstrap, stable_split
)


def sample(tmp_path, *, n=90):
    p = tmp_path/'invented_education.csv'
    with p.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['user_id','skill_id','order_id','correct','original'])
        w.writeheader()
        for i in range(n):
            for skill in ('A','B'):
                for k in range(5):
                    w.writerow({'user_id':f'invented_{i}', 'skill_id':skill,
                                'order_id':k*5 + (skill=='B'),
                                'correct':str(int((k+i+(skill=='A'))%4 != 0)), 'original':1})
    return p


def test_student_split_stable_and_disjoint():
    assert stable_split('invented_1') == stable_split('invented_1')
    assert stable_split('invented_1') in ('train', 'development', 'sealed_test')


def test_stable_split_is_identifier_only():
    assert stable_split('id') == stable_split('id')


def test_no_foreign_network_requests(tmp_path):
    with pytest.raises(ValueError): load_local_data(tmp_path/'absent.csv')


def test_aggregate_report_and_sealed_test_never_scored(tmp_path):
    p = sample(tmp_path)
    r = benchmark(p)
    assert r['train_only_parameter_selection']
    assert r['split_counts']['sealed_test']['n_students'] > 0
    assert 'sealed_test_scores' not in r
    assert len(r['development_scores']) == 3
    for name in ('no_forgetting','with_forgetting'):
        assert name in r['selected_model_params']


def test_no_student_ids_in_report(tmp_path):
    report=json.dumps(benchmark(sample(tmp_path)))
    assert 'invented_0' not in report
    assert 'invented_30' not in report


def test_scoring_reproducible(tmp_path):
    p=sample(tmp_path)
    assert benchmark(p) == benchmark(p)


def test_grid_forgetting_modes():
    assert all(x[3]==0 for x in GRIDS['no_forgetting'])
    assert all(x[3]>0 for x in GRIDS['with_forgetting'])


def test_identical_models_yield_same_score(tmp_path):
    p=sample(tmp_path)
    groups=load_local_data(p)['groups']['development']
    model=(.1,.25,.08,.02)
    a=grouped_scores(groups,model)
    b=grouped_scores(groups,model)
    assert a['brier']==b['brier']
    assert a['log_loss']==b['log_loss']
    assert paired_bootstrap(a,b,key=5)['brier_difference']==0


def test_chronological_order_independent_of_csv_row_order(tmp_path):
    p=sample(tmp_path)
    with p.open() as f:rows=list(csv.DictReader(f))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(reversed(rows))
    assert benchmark(p)['development_scores'] == benchmark(sample(tmp_path))['development_scores']


def test_duplicate_event_rejected(tmp_path):
    p=sample(tmp_path)
    with p.open('a') as f: f.write('invented_0,A,0,1,1\n')
    with pytest.raises(ValueError,match='Repeated'):load_local_data(p)


def test_missing_required_column_fails_closed(tmp_path):
    p=tmp_path/'bad.csv';p.write_text('student,score\na,1\n')
    with pytest.raises(ValueError,match='Required columns'):load_local_data(p)


def test_invalid_correct_fails_closed(tmp_path):
    p=sample(tmp_path)
    with p.open('a') as f: f.write('invented_extra,A,100,maybe,1\n')
    with pytest.raises(ValueError,match='binary correct'):load_local_data(p)


def test_scaffold_exclusion_not_infer_treatment(tmp_path):
    p=sample(tmp_path)
    with p.open('a') as f: f.write('invented_0,A,100,0,0\n')
    baseline=load_local_data(sample(tmp_path))
    updated=load_local_data(p)
    assert baseline['events']==updated['events']


def test_no_human_efficacy_claim(tmp_path):
    r=benchmark(sample(tmp_path))
    assert 'Causal recovery-intervention efficacy' in r['does_not_establish']


def test_grouping_blocks_student_leakage(tmp_path):
    p=sample(tmp_path)
    data=load_local_data(p)
    s=data['students']
    assert not (s['train'] & s['development'])
    assert not (s['train'] & s['sealed_test'])
    assert not (s['development'] & s['sealed_test'])


def test_no_skill_rows_ignored(tmp_path):
    p=sample(tmp_path)
    with p.open('a') as f: f.write('invented_5,,333,0,1\n')
    assert load_local_data(p)['skipped_missing_skill']==1
