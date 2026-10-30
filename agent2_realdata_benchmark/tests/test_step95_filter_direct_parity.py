"""Direct parity of committed TwoStateFilter vs independent path enumeration.

Only short enumerations. Uses NO held-out participant/environment seeds.
"""
from itertools import product
import math
import random

import pytest

from src.prototype.step95_bayesian_forgetting_filter import (
    Model, TwoStateFilter, stream, compare_forgetting_models,
)
from scripts.step95_filter_calibration_development import ReferenceFilter, Rates
from scripts.step95_filter_path_oracle import enumerate_paths


def compare_steps(responses, learning, *, initial=.75, slip=.1, guess=.25, forget=.02):
    expected = enumerate_paths(responses, learning, initial_mastery=initial,
                               slip=slip, guess=guess, forget=forget)
    actual = stream(Model(slip=slip, guess=guess, forget=forget), responses,
                    learning, initial_mastery=initial)
    assert len(expected) == len(actual)
    fields = (
        ("index", "index"),
        ("prior_mastery", "prior_mastery"),
        ("posterior_mastery", "posterior_mastery"),
        ("posterior_recent_forgetting", "recent_forgetting_posterior"),
        ("predictive_next_mastery", "predictive_next_mastery"),
        ("observation_likelihood", "observation_likelihood"),
        ("cumulative_log_likelihood", "cumulative_log_likelihood"),
    )
    for i, (got, oracle) in enumerate(zip(actual, expected)):
        assert got.response is responses[i]
        for name, oracle_name in fields:
            gv = getattr(got, name)
            ev = getattr(oracle, oracle_name)
            if name == "index":
                assert gv == ev
            else:
                assert math.isclose(gv, ev, rel_tol=2e-12, abs_tol=2e-12), (
                    f"step {i}: {name} differs, got {gv}, oracle {ev}, answers {responses}"
                )
        assert 0 <= got.posterior_recent_forgetting <= 1 - got.posterior_mastery + 2e-12
    return actual


@pytest.mark.parametrize("response_pattern", list(product((True, False, None), repeat=4)))
def test_all_short_response_patterns_against_exact_paths(response_pattern):
    compare_steps(response_pattern, (.0, .05, .10, .2))


@pytest.mark.parametrize("params", [
    (.25, .10, .25, 0.0),
    (.75, .10, .25, .02),
    (.40, .25, .25, .08),
    (.60, .75, .25, .50),  # Completely non-informative responses
    (1.0, .10, .25, .10),
    (0.0, .10, .25, 1.0),
])
def test_boundary_and_misspecified_rate_regimes(params):
    initial, slip, guess, forget = params
    compare_steps((True, None, False, True, False),
                  (0.0, .25, 1.0, .0, .1),
                  initial=initial, slip=slip, guess=guess, forget=forget)


def test_longer_seeded_short_trajectories_against_exact_oracle():
    rng = random.Random(719951)
    for _ in range(64):
        n = rng.randint(1, 7)
        responses = tuple(rng.choice((True, False, None)) for _ in range(n))
        learning = tuple(rng.choice((0.0, .02, .10, .75, 1.0)) for _ in range(n))
        params = dict(initial=rng.choice((0.0, .10, .25, .75, 1.0)),
                      slip=rng.choice((.0, .10, .25, .75)),
                      guess=rng.choice((.10, .25, .75, 1.0)),
                      forget=rng.choice((0.0, .02, .10, .50, 1.0)))
        # Some extreme combinations may imply an impossible observation.
        try:
            expected = enumerate_paths(responses, learning,
                                       initial_mastery=params["initial"],
                                       slip=params["slip"], guess=params["guess"],
                                       forget=params["forget"])
        except ValueError as exc:
            if "impossible" not in str(exc):
                raise
            with pytest.raises(ValueError, match="impossible"):
                stream(Model(params["slip"], params["guess"], params["forget"]),
                       responses, learning, params["initial"])
        else:
            assert expected
            compare_steps(responses, learning, **params)


def test_external_calibration_reference_agrees_on_constant_learning():
    rates = Rates(forget=.02, learn=.05, slip=.10, guess=.25,
                  initial_mastery=.75)
    ref = ReferenceFilter(rates)
    user = TwoStateFilter(Model(slip=.10, guess=.25, forget=.02), initial_mastery=.75)
    for index, response in enumerate((True, False, None, False, True, True)):
        expected = ref.step(response)
        actual = user.step(response, learn=.05)
        assert math.isclose(actual.prior_mastery, expected.mastery_prior, abs_tol=1e-12)
        assert math.isclose(actual.posterior_mastery, expected.mastery_posterior, abs_tol=1e-12)
        assert math.isclose(actual.observation_likelihood,
                            (1.0 if response is None else
                             expected.mastery_prior *
                             ((.9 if response else .1)) +
                             (1 - expected.mastery_prior) *
                             ((.25 if response else .75))), abs_tol=1e-12)
        if index == 0:
            assert actual.posterior_recent_forgetting == 0
            assert expected.last_transition_forgetting_posterior is None
        else:
            assert math.isclose(actual.posterior_recent_forgetting,
                                expected.last_transition_forgetting_posterior,
                                abs_tol=1e-12)


@pytest.mark.parametrize("pattern", [
    (), (True,), (False,), (None,), (True, False, None, True),
    (False, False, True, False, True), (None, None, None),
])
def test_model_comparison_matches_independent_exact_likelihood(pattern):
    learning = tuple(.1 if i % 2 else .0 for i in range(len(pattern)))
    prior_H1 = .37
    obj = compare_forgetting_models(pattern, learning, slip=.10, guess=.25,
                                    alternative_forgetting=.08, initial_mastery=.65,
                                    prior_alternative_model=prior_H1)
    two = [enumerate_paths(pattern, learning, initial_mastery=.65,
                           slip=.10, guess=.25, forget=f)
           for f in (0.0, .08)]
    ll0 = two[0][-1].cumulative_log_likelihood if pattern else 0
    ll1 = two[1][-1].cumulative_log_likelihood if pattern else 0
    bf = ll1 - ll0
    prior_odds = prior_H1 / (1 - prior_H1)
    posterior = math.exp(bf) * prior_odds / (1 + math.exp(bf) * prior_odds)
    assert math.isclose(obj.log_evidence_null, ll0, abs_tol=1e-12)
    assert math.isclose(obj.log_evidence_alternative, ll1, abs_tol=1e-12)
    assert math.isclose(obj.log_bayes_factor_forgetting_vs_no_forgetting,
                        bf, abs_tol=1e-12)
    assert math.isclose(obj.posterior_probability_of_forgetting_model,
                        posterior, abs_tol=1e-12)


def test_non_informative_emissions_have_bayes_factor_one():
    for responses in ((True, False, False, True), (None, True, None, False)):
        result = compare_forgetting_models(responses, (.2, .1, .3, .0),
                                           slip=.75, guess=.25,
                                           alternative_forgetting=.4,
                                           initial_mastery=.8,
                                           prior_alternative_model=.3)
        assert abs(result.log_bayes_factor_forgetting_vs_no_forgetting) < 1e-12
        assert result.posterior_probability_of_forgetting_model == pytest.approx(.3)


def test_initially_unmastered_cannot_have_recent_forgetting_without_learning():
    results = compare_steps((True, False, True, False), (0.0,) * 4,
                            initial=0.0, slip=.1, guess=.25, forget=.8)
    assert all(x.posterior_recent_forgetting == 0 for x in results)


def test_missing_observation_applies_transition_without_an_emission():
    results = compare_steps((None, None, None), (.3, .0, .1),
                            initial=.7, slip=.1, guess=.25, forget=.15)
    assert all(x.observation_likelihood == 1 for x in results)
    assert all(x.cumulative_log_likelihood == 0 for x in results)


def test_impossible_observation_does_not_mutate_filter():
    f = TwoStateFilter(Model(slip=1.0, guess=0.0, forget=.1), initial_mastery=1.0)
    snapshot = (f.mastery, f._incoming_forgetting_mass, f.log_evidence, f.n_steps)
    with pytest.raises(ValueError, match="impossible"):
        f.step(True, learn=.2)
    assert (f.mastery, f._incoming_forgetting_mass, f.log_evidence, f.n_steps) == snapshot


def test_invalid_input_rejected():
    with pytest.raises(ValueError, match="probability"):
        TwoStateFilter(Model(), initial_mastery=-.1)
    with pytest.raises(ValueError, match="learn"):
        TwoStateFilter(Model()).step(True, learn=1.1)
    with pytest.raises(ValueError, match="response"):
        TwoStateFilter(Model()).step(1)
    with pytest.raises(ValueError, match="one action interval"):
        stream(Model(), (True, False), (.1,))


def test_recent_forgetting_event_is_distinct_from_hypothesis_posterior():
    responses = (True, True, False, False)
    model = Model(forget=.02)
    flt = TwoStateFilter(model, initial_mastery=.75)
    for response in responses:
        last = flt.step(response, learn=0.0)
    comparison = compare_forgetting_models(
        responses, (0.0,) * 4, initial_mastery=.75,
        alternative_forgetting=.02,
    )
    assert last.posterior_recent_forgetting < .1
    assert comparison.posterior_probability_of_forgetting_model > .5
    assert comparison.posterior_probability_of_forgetting_model > last.posterior_recent_forgetting
