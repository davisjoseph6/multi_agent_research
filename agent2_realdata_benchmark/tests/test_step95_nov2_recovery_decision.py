"""Security/claims tests on invented aggregate-only mechanism reports."""
import json
from pathlib import Path

import pytest

from scripts.step95_nov2_recovery_decision import (
    SCENARIOS, COMPARATORS, SOURCE_PATHS, build_report, decision_from_results,
    positive_contrast, render_md, validate_realdata, verify_scenario,
)


def contrast(d=0.01,n=5):
    return {'mean':d,'descriptive_bootstrap_95pct_interval':[d-.001,d+.001],
            'n_paired_seeds':n,'wins':n if d>0 else 0,
            'ties':0 if d!=0 else n,'losses':n if d<0 else 0}


def audit(name,n=5,d=.01):
    names=('v6',*COMPARATORS)
    return {'manifest':{'scenario':name,'split':'development','seed_start':100000,'seed_end':100000+n-1,
                        'participants':n,'session_lengths':[20,20,15],
                        'v6_replayed_and_parity_verified':True,'no_heldout_seeds_accessed':True},
            'synthetic_only':True,'human_evidence':False,
            'descriptive_means':{key:{'true_mastery':.4,'nominal_net_mastery':.35,'resource_actions':2.0} for key in names},
            'paired_v6_minus':{key:contrast(d,n) for key in COMPARATORS},
            'v6_trigger_diagnostics':{'total_triggered_recovery_actions':3,
                                      'total_mastered_at_trigger':1,
                                      'total_unmastered_at_trigger':2,
                                      'total_lost_after_recorded_forgetting_at_trigger':1,
                                      'total_unmastered_without_recorded_forgetting':1}}


def fixture_root(tmp_path):
    for p in SOURCE_PATHS:
        f=tmp_path/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('test fixture, no real data\n')
    return tmp_path


def realdata():
    return {'models_selected_on_phase6_train_only':True, 'membership_exclusion_asserted':True,
            'phase6_test_labels_evaluated':0,
            'original_phase6_test_outcomes_used_in_this_run':False,
            'can_certify_clean_independent_heldout_generalization':False,
            'phase6_membership_counts':{'train':2951,'val':633,'test':633},
            'phase6_val_metrics':{
                'train_selected_with_forgetting':{'n_students':633,'n_observations':45488,'brier':.21,'log_loss':.61},
                'train_selected_no_forgetting':{'n_students':633,'n_observations':45488,'brier':.22,'log_loss':.63}}}


def test_valid_paired_and_interval():
    assert positive_contrast(contrast(),5)['descriptive_lower_bound_positive']


def test_reject_malformed_counts():
    a=contrast();a['ties']=100
    with pytest.raises(ValueError,match='accounting'):positive_contrast(a,5)


def test_reject_nonfinite():
    a=contrast();a['mean']=float('nan')
    with pytest.raises(ValueError):positive_contrast(a,5)


def test_reject_heldout_range():
    a=audit('slow_forgetting');a['manifest']['seed_start']=200000;a['manifest']['seed_end']=200004
    with pytest.raises(ValueError):verify_scenario('slow_forgetting',a,5)


def test_reject_sneaky_human_labels():
    a=audit('slow_forgetting');a['human_evidence']=True
    with pytest.raises(ValueError):verify_scenario('slow_forgetting',a,5)


def test_reject_missing_ablation():
    a=audit('slow_forgetting');del a['paired_v6_minus']['no_recovery']
    with pytest.raises(ValueError):verify_scenario('slow_forgetting',a,5)


def test_reject_fake_simulator_parity():
    a=audit('slow_forgetting');a['manifest']['v6_replayed_and_parity_verified']=False
    with pytest.raises(ValueError):verify_scenario('slow_forgetting',a,5)


def test_reject_trigger_inconsistency():
    a=audit('slow_forgetting');a['v6_trigger_diagnostics']['total_mastered_at_trigger']=10
    with pytest.raises(ValueError):verify_scenario('slow_forgetting',a,5)


def test_five_scenario_positive_screen():
    a={name:verify_scenario(name,audit(name),5) for name in SCENARIOS}
    d=decision_from_results(a)
    assert d['conservative_predeclared_screening_pass'] is True
    assert d['independent_algorithmic_novelty_established'] is False
    assert d['real_student_intervention_effect_established'] is False


def test_one_negative_scenario_fails_screen():
    a={name:verify_scenario(name,audit(name, d= -.01 if name=='rapid_forgetting' else .01),5) for name in SCENARIOS}
    assert decision_from_results(a)['conservative_predeclared_screening_pass'] is False


def test_missing_scenario_fails():
    a={name:verify_scenario(name,audit(name),5) for name in SCENARIOS[:-1]}
    with pytest.raises(ValueError):decision_from_results(a)


def test_phase6_clean_reanalysis_accepted():
    r=validate_realdata(realdata())
    assert r['forecast_better_with_forgetting_in_this_development_analysis']
    assert not r['causal_recovery_efficacy_established']
    assert not r['independent_heldout_generalization_established']


def test_reject_phase6_test_peek():
    r=realdata();r['phase6_test_labels_evaluated']=1
    with pytest.raises(ValueError):validate_realdata(r)


def test_reject_unsupported_clean_holdout_claim():
    r=realdata();r['can_certify_clean_independent_heldout_generalization']=True
    with pytest.raises(ValueError):validate_realdata(r)


def test_reject_mismatched_evaluation_population():
    r=realdata();r['phase6_val_metrics']['train_selected_with_forgetting']['n_observations']=50000
    with pytest.raises(ValueError):validate_realdata(r)


def test_source_hashes_and_no_overstated_claims(tmp_path):
    root=fixture_root(tmp_path)
    audits={name:audit(name) for name in SCENARIOS}
    r=build_report(participants=5,realdata=realdata(),root=root,audits=audits)
    assert set(r['source_sha256'])==set(SOURCE_PATHS)
    assert not r['original_step95_exit_criterion_completed']
    assert not r['original_52_step_rubric_modified']
    assert r['real_data_context']['n_val_observations']==45488
    assert 'NOT HUMAN EFFICACY' in render_md(r)
    assert 'novelty' in json.dumps(r).lower()


def test_missing_source_fails(tmp_path):
    with pytest.raises(ValueError,match='Missing existing source'):
        build_report(participants=5,realdata=None,root=tmp_path,audits={})


def test_reject_underpowered_two_seeds(tmp_path):
    with pytest.raises(ValueError,match='3..1000'):
        build_report(participants=2,realdata=None,root=tmp_path,audits={})
