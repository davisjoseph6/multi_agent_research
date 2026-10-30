"""Development-only exact HMM examples; no simulator and no held-out data."""
import json
from src.prototype.step95_bayesian_forgetting_filter import (
    Model, stream, compare_forgetting_models,
)


def main() -> None:
    patterns = {
        'V6_flag_pattern_CCWW': [True, True, False, False],
        'all_correct_CCCC': [True] * 4,
        'all_wrong_WWWW': [False] * 4,
    }
    examples = {}
    for name, responses in patterns.items():
        rates = [0.0] * len(responses)
        baseline = stream(Model(slip=.1, guess=.25, forget=.02), responses, rates,
                          initial_mastery=.75)
        comparison = compare_forgetting_models(
            responses, rates, slip=.1, guess=.25, alternative_forgetting=.02,
            initial_mastery=.75,
        )
        examples[name] = {
            'mastery_posterior_at_last_response': baseline[-1].posterior_mastery,
            'last_transition_forgetting_posterior': baseline[-1].posterior_recent_forgetting,
            'posterior_of_forgetting_MODEL': comparison.posterior_probability_of_forgetting_model,
            'log_bayes_factor_H1_over_H0': comparison.log_bayes_factor_forgetting_vs_no_forgetting,
        }
    print(json.dumps({
        'synthetic_analytical_baseline_only': True,
        'human_data': False,
        'model_assumptions': {'slip': .1, 'guess': .25, 'forget_H1': .02,
                              'forget_H0': 0, 'initial_mastery': .75, 'learn_per_step': 0.0},
        'examples': examples,
        'heldout_seeds_accessed': False,
        'warning': 'Model-based probabilities depend on assumed parameters; neither a wrong-answer run nor H1 posterior proves true forgetting.',
    }, indent=2))


if __name__ == '__main__':
    main()
