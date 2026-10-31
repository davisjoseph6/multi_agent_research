"""Step103: exact limits of post-only forgetting identification.

The two *deliberately restricted* hypotheses are:
 F: mastery was certain at a hidden pre-transition time, and the concept
    was subsequently forgotten with probability f;
 L: the concept was initially mastered with probability 1-f, with no
    forgetting event.

After the transition both have the SAME latent mastery distribution,
and under the fixed-state / identical-response-model assumptions their
later observations are distributionally identical. This DOES NOT assert
general BKT or hidden Markov models are non-identifiable.

All probabilities below are exact Fractions. This is elementary model
analysis, NOT a novel theorem, real student outcome, or approved intervention.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import product

DEFAULT_SLIP = Fraction(1, 10)
DEFAULT_GUESS = Fraction(1, 4)


def valid_rate(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError("Specify probabilities as int, rational string or Fraction")
    try:
        v = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError("Invalid rational probability") from error
    if not 0 <= v <= 1:
        raise ValueError("Probability outside [0,1]")
    return v


def observation_prob(
    mastered: bool, correct: bool, *,
    slip: Fraction = DEFAULT_SLIP, guess: Fraction = DEFAULT_GUESS,
) -> Fraction:
    if type(mastered) is not bool or type(correct) is not bool:
        raise ValueError("Observations and states must be Boolean")
    s, g = valid_rate(slip), valid_rate(guess)
    p = 1 - s if mastered else g
    return p if correct else 1 - p


def emission_sequence(
    mastered: bool, answers: tuple[bool, ...], *,
    slip: Fraction = DEFAULT_SLIP, guess: Fraction = DEFAULT_GUESS,
) -> Fraction:
    if not isinstance(answers, tuple):
        raise ValueError("Answers must be an ordered Boolean tuple")
    out = Fraction(1)
    for answer in answers:
        out *= observation_prob(mastered, answer, slip=slip, guess=guess)
    return out


def distributions(
    *, forget_probability: object, post_questions: int,
    observed_pre_question: bool = False,
    slip: object = DEFAULT_SLIP,
    guess: object = DEFAULT_GUESS,
) -> tuple[dict[tuple[bool, ...], Fraction], dict[tuple[bool, ...], Fraction]]:
    """Enumerate probabilities under F (forgotten) and L (initially weak).

    F: pretransition state is mastered with probability one. Optional
    pretransition response is emitted from that mastered state. Then with
    probability f it becomes unmastered. It remains fixed for all post
    responses. L: pretransition mastery is Bernoulli(1-f), stays fixed,
    and has the identical emission probabilities.

    This is a *conditional boundary case*, not a real forgetting detector:
    no feedback, no learning, no later forgetting, no changing difficulty.
    """
    f, s, g = [valid_rate(v) for v in (forget_probability, slip, guess)]
    if type(post_questions) is not int or not 0 <= post_questions <= 12:
        raise ValueError("Only 0..12 post questions can be enumerated")
    if type(observed_pre_question) is not bool:
        raise ValueError("Invalid prequestion flag")
    f_dist: dict[tuple[bool, ...], Fraction] = {}
    low_dist: dict[tuple[bool, ...], Fraction] = {}
    n = post_questions + int(observed_pre_question)
    for responses in product((False, True), repeat=n):
        after = responses[1:] if observed_pre_question else responses
        m_post = emission_sequence(True, after, slip=s, guess=g)
        u_post = emission_sequence(False, after, slip=s, guess=g)
        post_mixture = (1 - f) * m_post + f * u_post
        if observed_pre_question:
            pre = responses[0]
            m_pre = observation_prob(True, pre, slip=s, guess=g)
            u_pre = observation_prob(False, pre, slip=s, guess=g)
            f_dist[responses] = m_pre * post_mixture
            low_dist[responses] = (
                (1 - f) * m_pre * m_post + f * u_pre * u_post
            )
        else:
            f_dist[responses] = post_mixture
            low_dist[responses] = post_mixture
    if (sum(f_dist.values(), Fraction(0)) != 1
            or sum(low_dist.values(), Fraction(0)) != 1):
        raise AssertionError("Observation distribution failed to normalize")
    return f_dist, low_dist


def total_variation(a: dict, b: dict) -> Fraction:
    if set(a) != set(b) or not a:
        raise ValueError("Distributions must have equal, nonempty support")
    if any(valid_rate(v) != v for v in (*a.values(), *b.values())):
        raise ValueError("Malformed probability")
    if sum(a.values(), Fraction(0)) != 1 or sum(b.values(), Fraction(0)) != 1:
        raise ValueError("Distributions are not normalized")
    return sum((abs(a[x] - b[x]) for x in a), Fraction(0)) / 2


def exact_identification_report(
    *, forget_probability: object = Fraction(1, 4),
    post_questions: int = 3, slip: object = DEFAULT_SLIP,
    guess: object = DEFAULT_GUESS,
) -> dict:
    """Compute optimal equal-prior hypothesis test error in the toy model."""
    f, s, g = [valid_rate(v) for v in (forget_probability, slip, guess)]
    post_only = distributions(
        forget_probability=f, post_questions=post_questions,
        observed_pre_question=False, slip=s, guess=g,
    )
    pre_and_post = distributions(
        forget_probability=f, post_questions=post_questions,
        observed_pre_question=True, slip=s, guess=g,
    )
    tv_post = total_variation(*post_only)
    tv_pre = total_variation(*pre_and_post)
    # Under specified fixed-state assumptions, post-only experiments are
    # observationally equivalent for ANY number of questions.
    if tv_post != 0:
        raise AssertionError("Post-only observational equivalence violated")
    # In this narrow pair of models, one recorded pre-response separates
    # hypotheses only through the previously learned-versus-weak baseline.
    expected = f * abs((1 - s) - g)
    if tv_pre != expected:
        raise AssertionError("Recorded-pretest total variation mismatch")
    return {
        "scope": "EXACT_HIDDEN_PRETRANSITION_HISTORY_EXAMPLE_ONLY",
        "novel_identifiability_theorem_established": False,
        "general_bkt_nonidentifiable": False,
        "human_learning_evidence": False,
        "forget_probability": str(f),
        "slip": str(s), "guess": str(g),
        "post_questions": post_questions,
        "post_only_total_variation": str(tv_post),
        "post_only_optimal_equal_prior_error": str((1 - tv_post) / 2),
        "one_prequestion_plus_post_total_variation": str(tv_pre),
        "one_prequestion_plus_post_optimal_equal_prior_error": str((1 - tv_pre) / 2),
        "qualifications": [
            "Histories before the post-only comparison are entirely unobserved.",
            "No new learning, forgetting, or action-dependent response effects after the comparison time.",
            "The observed prequestion occurs before the hypothetical forgetting event.",
            "The pair has identical current-state distributions but different possible prior histories.",
            "This special-case example does not contradict generic HMM/BKT identifiability results.",
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(exact_identification_report(), indent=2))
