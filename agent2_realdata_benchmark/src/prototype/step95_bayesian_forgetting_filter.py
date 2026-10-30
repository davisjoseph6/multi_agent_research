"""Exact two-state filtering baseline with action-dependent learning and forgetting.

Research baseline ONLY, not a novel algorithm, not calibrated to learners.
All probabilities are assumed, not inferred. No latent truth is supplied.

Time convention for each step t:
  1. S_t is the unobserved mastery state immediately BEFORE a response.
  2. Observe Y_t (or None); update P(S_t=mastered | data).
  3. Apply an action with learning probability L_t and interval forgetting F:
     mastered -> unknown with probability F;
     unknown -> mastered with probability L_t.
  4. Predict S_(t+1). A mastery loss and new learning are mutually exclusive
     transitions of the same two-state Markov chain during this interval.

The 'recent forgetting' posterior at t refers to the immediately PRECEDING
transition (t-1 -> t). It must not be confused with P(S_t=unknown), the
probability of ever having forgotten, or proof of a real forgetting event.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log, log1p
from typing import Sequence


def probability(x: float, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) or not 0 <= x <= 1:
        raise ValueError(f"{name} must be a finite probability in [0,1]")
    return float(x)


@dataclass(frozen=True)
class Model:
    slip: float = .10
    guess: float = .25
    forget: float = .02

    def __post_init__(self) -> None:
        for field in ('slip', 'guess', 'forget'):
            probability(getattr(self, field), field)


@dataclass(frozen=True)
class Step:
    index: int
    response: bool | None
    prior_mastery: float
    posterior_mastery: float
    posterior_recent_forgetting: float
    predictive_next_mastery: float
    observation_likelihood: float
    cumulative_log_likelihood: float


class TwoStateFilter:
    def __init__(self, model: Model, initial_mastery: float = .25):
        if not isinstance(model, Model):
            raise TypeError('model must be Model')
        self.model = model
        self.mastery = probability(initial_mastery, 'initial_mastery')
        self._incoming_forgetting_mass = 0.0
        self.log_evidence = 0.0
        self.n_steps = 0

    def step(self, response: bool | None, learn: float = 0.0) -> Step:
        """One response (possibly missing) and one subsequent action interval.

        'learn' is the unknown-to-mastered probability of the actual action,
        NOT a parameter estimated from the response. A non-question resource
        may use response=None. Exactly one step represents one transition.
        """
        learning = probability(learn, 'learn')
        if response is not None and type(response) is not bool:
            raise ValueError('response must be bool or None')
        p = self.mastery
        if response is None:
            mastered_likelihood = unknown_likelihood = 1.0
        elif response:
            mastered_likelihood = 1.0 - self.model.slip
            unknown_likelihood = self.model.guess
        else:
            mastered_likelihood = self.model.slip
            unknown_likelihood = 1.0 - self.model.guess
        z = p * mastered_likelihood + (1.0-p) * unknown_likelihood
        if z <= 0.0:
            raise ValueError('response impossible under this model; state unchanged')

        post = p * mastered_likelihood / z
        # The previous transition's forgetting event implies current unknown.
        # Bayes conditioning on the current response (or no response).
        recent = self._incoming_forgetting_mass * unknown_likelihood / z
        next_p = post * (1.0 - self.model.forget) + (1.0-post) * learning

        self.mastery = min(1.0, max(0.0, next_p))
        self._incoming_forgetting_mass = post * self.model.forget
        self.log_evidence += log(z)
        self.n_steps += 1
        return Step(
            index=self.n_steps-1, response=response, prior_mastery=p,
            posterior_mastery=post,
            posterior_recent_forgetting=recent,
            predictive_next_mastery=self.mastery,
            observation_likelihood=z,
            cumulative_log_likelihood=self.log_evidence,
        )


def stream(model: Model, responses: Sequence[bool | None],
           learning_probabilities: Sequence[float], initial_mastery: float = .25) -> tuple[Step, ...]:
    if len(responses) != len(learning_probabilities):
        raise ValueError('one action interval required per time step')
    flt = TwoStateFilter(model, initial_mastery)
    return tuple(flt.step(y, learn) for y, learn in zip(responses, learning_probabilities))


@dataclass(frozen=True)
class ModelComparison:
    log_bayes_factor_forgetting_vs_no_forgetting: float
    posterior_probability_of_forgetting_model: float
    log_evidence_null: float
    log_evidence_alternative: float


def compare_forgetting_models(
    responses: Sequence[bool | None],
    learning_probabilities: Sequence[float], *,
    slip: float = .1, guess: float = .25, alternative_forgetting: float = .02,
    initial_mastery: float = .25, prior_alternative_model: float = .5,
) -> ModelComparison:
    """Compare FIXED known models H0:F=0 and H1:F=specified, by likelihood.

    The result is the probability of a MODEL under assumed model priors,
    NOT the probability of a particular latent forgetting event.
    It is not a fitted or empirically calibrated posterior.
    """
    pi = probability(prior_alternative_model, 'prior_alternative_model')
    if not 0 < pi < 1:
        raise ValueError('prior_alternative_model must be strictly interior')
    null = stream(Model(slip, guess, 0.0), responses, learning_probabilities, initial_mastery)
    alternative = stream(Model(slip, guess, alternative_forgetting),
                         responses, learning_probabilities, initial_mastery)
    ll0 = null[-1].cumulative_log_likelihood if null else 0.0
    ll1 = alternative[-1].cumulative_log_likelihood if alternative else 0.0
    log_bf = ll1 - ll0
    log_odds = log(pi) - log1p(-pi) + log_bf
    if log_odds >= 0:
        p = 1.0 / (1.0 + exp(-log_odds))
    else:
        e = exp(log_odds)
        p = e / (1.0 + e)
    return ModelComparison(log_bf, p, ll0, ll1)
