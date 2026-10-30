"""Exact latent-path and development-only calibration reference checks."""
from itertools import product
from math import isclose

import pytest

from scripts.step95_filter_calibration_development import (
    DEV_START, HELDOUT_START, Rates, ReferenceFilter, WORLDS,
    simulate, one_run, score, benchmark, calibration_bins, brier, uniform,
)


def enumerate_latent_reference(r: Rates, responses: tuple[bool | None, ...]):
    """Direct sum over 2^n latent paths; deliberately independent of filter."""
    weights = []
    for states in product((False, True), repeat=len(responses)):
        prior = r.initial_mastery if states[0] else 1-r.initial_mastery
        for i, y in enumerate(responses):
            if y is not None:
                p_correct = 1-r.slip if states[i] else r.guess
                prior *= p_correct if y else 1-p_correct
            if i < len(states)-1:
                a, b = states[i], states[i+1]
                transition = ((1-r.forget) if b else r.forget) if a else (r.learn if b else 1-r.learn)
                prior *= transition
        weights.append((states, prior))
    denominator = sum(w for _, w in weights)
    if denominator == 0:
        raise ValueError("impossible response sequence")
    last_mastery = sum(w for states,w in weights if states[-1])/denominator
    last_forget = (sum(w for states,w in weights if len(states)>=2 and states[-2] and not states[-1])/denominator
                   if len(responses)>1 else None)
    return last_mastery, last_forget


@pytest.mark.parametrize('r', (
    Rates(.02,.05,.10), Rates(.08,.02,.25), Rates(0,0,.10),
    Rates(.20,.30, .25,.25,.50),
))
def test_exact_filter_matches_latent_path_enumeration(r):
    for n in range(1,5):
        for responses in product((True,False), repeat=n):
            f=ReferenceFilter(r)
            output=None
            for y in responses:output=f.step(y)
            mastery,event=enumerate_latent_reference(r,responses)
            assert isclose(output.mastery_posterior,mastery,abs_tol=1e-12)
            if event is None:assert output.last_transition_forgetting_posterior is None
            else:assert isclose(output.last_transition_forgetting_posterior,event,abs_tol=1e-12)


def test_missing_response_does_not_count_as_wrong():
    f=ReferenceFilter(Rates(.02,.05,.1))
    first=f.step(None)
    assert first.mastery_posterior==.75
    assert first.response_prediction > .25
    second=f.step(None)
    assert second.mastery_posterior==pytest.approx(.75*(1-.02)+.25*.05)
    assert second.last_transition_forgetting_posterior==pytest.approx(.75*.02)


def test_impossible_observations_rejected():
    f=ReferenceFilter(Rates(forget=0,learn=0,slip=0,guess=0,initial_mastery=1))
    with pytest.raises(ValueError,match='impossible'):
        f.step(False)


def test_uninformative_observations_do_not_update_belief():
    f=ReferenceFilter(Rates(.20,.05,.75,.25,.50))
    assert f.step(True).mastery_posterior==pytest.approx(.5)
    previous=f.prior
    assert f.step(False).mastery_posterior==pytest.approx(previous)


def test_no_forgetting_implies_zero_event_posterior():
    f=ReferenceFilter(Rates(0,.05,.10))
    for y in (True,False,False,True,True,False):
        event=f.step(y).last_transition_forgetting_posterior
        assert event is None or event == 0


def test_zero_initial_mastery_zero_learning_implies_no_forgetting():
    f=ReferenceFilter(Rates(.8,0,.1,.25,0))
    for y in (True,True,False,False):
        r=f.step(y)
        assert r.mastery_posterior==0
        assert r.last_transition_forgetting_posterior is None or r.last_transition_forgetting_posterior==0


def test_true_world_simulation_never_forgets_without_forgetting_rate():
    for seed in range(DEV_START,DEV_START+10):
        rows=simulate(WORLDS['stationary'],seed,30)
        assert all(not event for _,_,event in rows)


def test_all_lost_events_have_prior_mastery_by_construction():
    r=Rates(1.0,0,.1,.25,1.0)
    rows=simulate(r,DEV_START,5)
    assert rows[0][0] is True and rows[0][2] is False
    assert rows[1][0] is False and rows[1][2] is True
    assert sum(row[2] for row in rows)==1


@pytest.mark.parametrize('invalid', (DEV_START-1,HELDOUT_START,HELDOUT_START+100,True,1.1))
def test_no_heldout_or_invalid_seeds(invalid):
    with pytest.raises(ValueError):uniform(invalid,0,'response')


@pytest.mark.parametrize('name', list(WORLDS))
def test_simulation_reproducibility(name):
    assert simulate(WORLDS[name],DEV_START,18)==simulate(WORLDS[name],DEV_START,18)


def test_filter_records_have_no_policy_actions_or_resource_access():
    rows=one_run(WORLDS['slow_forgetting'],WORLDS['slow_forgetting'],DEV_START,8)
    assert len(rows)==8
    assert rows[0]['forgetting_posterior'] is None
    assert len([r for r in rows if r['forgetting_posterior'] is not None])==7
    assert all('action' not in r and 'budget' not in r for r in rows)


def test_scoring_is_valid_and_calibration_counts_match():
    rows=one_run(WORLDS['slow_forgetting'],WORLDS['slow_forgetting'],DEV_START,10)
    report=score(rows)
    assert report['n_responses']==10
    assert sum(b['count'] for b in report['response_calibration_bins'])==10
    assert sum(b['count'] for b in report['forgetting_event_calibration_bins_oracle_only'])==9
    assert 0 <= report['response_prequential_brier'] <= 1


def test_well_specified_world_has_better_expected_brier_than_no_forgetting_on_large_development_sample():
    report=benchmark('slow_forgetting',300,30)
    a=report['summary']['oracle_parameters']['response_prequential_brier']
    b=report['summary']['stationary_no_forgetting']['response_prequential_brier']
    assert a < b
    assert report['manifest']['heldout_seeds_accessed'] is False


def test_development_report_exactly_reproducible():
    assert benchmark('rapid_forgetting',3,5)==benchmark('rapid_forgetting',3,5)


def test_invalid_configuration_rejected():
    with pytest.raises(ValueError):benchmark('unknown',10,5)
    with pytest.raises(ValueError):benchmark('slow_forgetting',0,5)
    with pytest.raises(ValueError):benchmark('slow_forgetting',10,1)
    with pytest.raises(ValueError):benchmark('slow_forgetting',3001,5)


@pytest.mark.parametrize('params', [
    dict(forget=-.1,learn=.1,slip=.1),dict(forget=.1,learn=1.1,slip=.1),
    dict(forget=.1,learn=.1,slip=float('nan')),
    dict(forget=.1,learn=.1,slip=True),
])
def test_invalid_rates_rejected(params):
    with pytest.raises(ValueError):Rates(**params)


def test_response_brier_known_cases():
    assert brier(0,0)==0
    assert brier(1,1)==0
    assert brier(.25,1)==pytest.approx(.5625)


def test_reference_does_not_claim_filter_source_identity():
    report=benchmark('slow_forgetting',2,3)
    assert report['reference_is_independent_of_existing_filter_source'] is True
    assert report['human_evidence'] is False


def test_paired_intervals_are_per_independent_seed():
    report=benchmark('slow_forgetting',7,9)
    comp=report['paired_oracle_comparisons']['oracle_minus_stationary_no_forgetting_response_brier']
    assert comp['n_seeds']==7
    assert comp['independent_units']=='synthetic_learner_seed'
    assert len(comp['descriptive_95pct_interval'])==2
    assert comp['descriptive_95pct_interval'][0] <= comp['descriptive_95pct_interval'][1]


def test_paired_interval_resampling_is_reproducible():
    from scripts.step95_filter_calibration_development import paired_bootstrap
    x=[.02,.09,-.10,.12]
    assert paired_bootstrap(x)==paired_bootstrap(x)
    assert paired_bootstrap([.5])['descriptive_95pct_interval']==[.5,.5]
