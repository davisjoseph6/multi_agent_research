"""Exact inference invariants and exhaustive small-state enumeration."""
from itertools import product
import math
import pytest

from src.prototype.step95_bayesian_forgetting_filter import (
    Model, TwoStateFilter, compare_forgetting_models, probability, stream,
)


def exhaustive(model, responses, rates, prior):
    """Enumerate all 2^(n+1) latent state paths; independent from filter code."""
    n = len(responses)
    z_total = z_current_mastered = z_next_mastered = z_recent_forget = 0.0
    for states in product((False, True), repeat=n+1):
        mass = prior if states[0] else 1-prior
        for i in range(n):
            known = states[i]
            y = responses[i]
            emission = (1-model.slip if known else model.guess) if y is True else (
                (model.slip if known else 1-model.guess) if y is False else 1.0)
            learning = rates[i]
            if known:
                transition = (1-model.forget) if states[i+1] else model.forget
            else:
                transition = learning if states[i+1] else 1-learning
            mass *= emission * transition
        z_total += mass
        if states[n-1]:
            z_current_mastered += mass
        if states[n]:
            z_next_mastered += mass
        if n >= 2 and states[n-2] and not states[n-1]:
            z_recent_forget += mass
    return z_total, z_current_mastered/z_total, z_next_mastered/z_total, z_recent_forget/z_total


def test_initial_prior_and_empty_stream():
    assert stream(Model(), [], [], .73) == ()
    assert TwoStateFilter(Model(), .73).mastery == .73


def test_observation_of_correct_increases_mastery_for_informative_emissions():
    x = TwoStateFilter(Model()).step(True, 0)
    assert x.posterior_mastery > x.prior_mastery


def test_observation_of_wrong_decreases_mastery_for_informative_emissions():
    x = TwoStateFilter(Model()).step(False, 0)
    assert x.posterior_mastery < x.prior_mastery


def test_observation_missing_is_not_incorrect():
    x = TwoStateFilter(Model(forget=.1), .6).step(None, .2)
    assert x.posterior_mastery == .6
    assert x.observation_likelihood == 1
    assert x.predictive_next_mastery == pytest.approx(.62)
    assert x.cumulative_log_likelihood == 0


def test_transition_formula_both_directions():
    x = TwoStateFilter(Model(forget=.15), .7).step(None, .3)
    assert x.predictive_next_mastery == pytest.approx(.7*.85 + .3*.3)


def test_forgetting_event_prior_initially_zero():
    x = TwoStateFilter(Model(forget=.3), .9).step(False, .0)
    assert x.posterior_recent_forgetting == 0


def test_zero_forgetting_implies_no_event_regardless_of_answers():
    xs = stream(Model(forget=0), [True, True, False, False], [0]*4, .8)
    assert all(x.posterior_recent_forgetting == 0 for x in xs)


def test_never_mastered_no_learning_cannot_forget():
    xs = stream(Model(forget=.8), [True, True, False, False], [0]*4, 0)
    assert all(x.posterior_recent_forgetting == 0 for x in xs)


def test_forgetting_posterior_bounded_by_current_nonmastery():
    xs = stream(Model(forget=.2), [True, True, False, False], [0]*4, .75)
    assert all(0 <= x.posterior_recent_forgetting <= 1-x.posterior_mastery + 1e-12 for x in xs)


def test_high_slip_equal_to_guess_has_no_information():
    model = Model(slip=.75, guess=.25, forget=.1)
    f = TwoStateFilter(model, .8)
    for y in [True, False, True, False]:
        x = f.step(y, .1)
        assert x.posterior_mastery == pytest.approx(x.prior_mastery)


def test_event_and_model_posterior_not_the_same_quantity():
    ys = [True, True, False, False]
    last = stream(Model(forget=.02), ys, [0]*4, .75)[-1]
    models = compare_forgetting_models(ys, [0]*4, initial_mastery=.75)
    assert last.posterior_recent_forgetting != pytest.approx(models.posterior_probability_of_forgetting_model)


def test_equal_models_zero_bayes_factor():
    cmp = compare_forgetting_models([True, False, False], [0, .1, .2],
                                    alternative_forgetting=0., prior_alternative_model=.35)
    assert cmp.log_bayes_factor_forgetting_vs_no_forgetting == pytest.approx(0.)
    assert cmp.posterior_probability_of_forgetting_model == pytest.approx(.35)


def test_model_comparison_empty_stream_preserves_prior():
    cmp = compare_forgetting_models([], [], prior_alternative_model=.3)
    assert cmp.log_bayes_factor_forgetting_vs_no_forgetting == 0
    assert cmp.posterior_probability_of_forgetting_model == pytest.approx(.3)


def test_normalized_likelihood_in_each_step():
    f = TwoStateFilter(Model())
    for y in (True, None, False):
        row = f.step(y, .14)
        assert 0 < row.observation_likelihood <= 1
        assert 0 <= row.posterior_mastery <= 1
        assert 0 <= row.predictive_next_mastery <= 1


def test_exhaustive_16_four_observation_strings_with_actions():
    model = Model(slip=.17, guess=.31, forget=.11)
    prior = .68
    actions = [.0, .25, .6, .08]
    for ys in product((True, False), repeat=4):
        xs = stream(model, ys, actions, prior)
        evidence, p_current, p_next, p_forget = exhaustive(model, ys, actions, prior)
        assert math.exp(xs[-1].cumulative_log_likelihood) == pytest.approx(evidence, abs=1e-13)
        assert xs[-1].posterior_mastery == pytest.approx(p_current, abs=1e-13)
        assert xs[-1].predictive_next_mastery == pytest.approx(p_next, abs=1e-13)
        assert xs[-1].posterior_recent_forgetting == pytest.approx(p_forget, abs=1e-13)


def test_exhaustive_missing_response_with_action():
    model = Model(slip=.1, guess=.25, forget=.14)
    ys = [True, None, False]
    rates = [.1, .4, 0]
    xs = stream(model, ys, rates, .35)
    evidence, p_current, p_next, p_forget = exhaustive(model, ys, rates, .35)
    assert math.exp(xs[-1].cumulative_log_likelihood) == pytest.approx(evidence)
    assert xs[-1].posterior_mastery == pytest.approx(p_current)
    assert xs[-1].predictive_next_mastery == pytest.approx(p_next)
    assert xs[-1].posterior_recent_forgetting == pytest.approx(p_forget)


def test_input_probabilities_reject_bad_values():
    for x in (-.1, 1.1, float('nan'), float('inf'), True, '0.2'):
        with pytest.raises(ValueError):
            probability(x, 'bad')


def test_impossible_response_raises_without_mutating_filter():
    f = TwoStateFilter(Model(slip=0., guess=0., forget=.2), 0.)
    with pytest.raises(ValueError, match='impossible'):
        f.step(True, 0.)
    assert f.mastery == 0
    assert f.n_steps == 0
    assert f.log_evidence == 0


def test_response_must_be_boolean_or_none():
    f = TwoStateFilter(Model())
    with pytest.raises(ValueError):
        f.step(1, .1)


def test_stream_requires_action_for_each_observation():
    with pytest.raises(ValueError):
        stream(Model(), [True, False], [.1])


def test_model_comparison_requires_interor_model_prior():
    with pytest.raises(ValueError):
        compare_forgetting_models([True], [0.], prior_alternative_model=1.)


def test_log_bayes_factor_is_difference_of_log_evidence():
    r = compare_forgetting_models([True, True, False, False], [0]*4,
                                  alternative_forgetting=.3, initial_mastery=.75)
    assert r.log_bayes_factor_forgetting_vs_no_forgetting == pytest.approx(
        r.log_evidence_alternative-r.log_evidence_null)
