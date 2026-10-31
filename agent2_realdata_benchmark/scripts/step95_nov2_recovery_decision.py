"""Fail-closed development-only V6 recovery ablation, paper-claim decision packet.

Invokes the EXISTING independent V6 mechanism audit on ALL five original
synthetic scenarios; verifies matched controllers/no-recovery comparisons;
records source hashes and combines with an existing aggregate-only Phase6
train/val report. Does not run held-out seeds, alter policy implementations,
fit on validation, inspect student-level data, or certify novelty/efficacy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess

SCENARIOS = (
    'stationary_nominal',
    'slow_forgetting',
    'rapid_forgetting',
    'noisy_slow_forgetting',
    'weak_learning',
)
COMPARATORS = ('no_recovery', 'no_risk_credit', 'no_coverage_weight', 'fixed', 'greedy')
SOURCE_PATHS = (
    'scripts/step95_v6_mechanism_audit.py',
    'scripts/step95_nonstationary_heldout.py',
    'scripts/step95_v6_development.py',
    'src/prototype/step95_v6_decline_candidate.py',
    'src/prototype/study_v3_pomcp.py',
    'src/prototype/study_v2.py',
    'src/prototype/step95_bayesian_forgetting_filter.py',
)


def sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def positive_contrast(value: dict, n: int) -> dict:
    """Independent shape/range checks. Not a statistical hypothesis test."""
    if not isinstance(value, dict):
        raise ValueError('Expected contrast mapping')
    d = value.get('mean')
    ci = value.get('descriptive_bootstrap_95pct_interval')
    wins, ties, losses = [value.get(x) for x in ('wins', 'ties', 'losses')]
    if not isinstance(d, (float, int)) or not math.isfinite(d):
        raise ValueError('Invalid contrast mean')
    if not isinstance(ci, list) or len(ci) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in ci):
        raise ValueError('Missing finite descriptive interval')
    if ci[0] > ci[1]:
        raise ValueError('Reversed confidence bounds')
    if any(type(x) is not int or x < 0 for x in (wins,ties,losses)) or sum((wins,ties,losses)) != n:
        raise ValueError('Invalid paired outcome accounting')
    return {'mean': float(d), 'descriptive_interval': ci, 'wins':wins, 'ties':ties, 'losses':losses,
            'descriptive_lower_bound_positive': ci[0] > 0,
            'mean_positive': d > 0}


def verify_scenario(name: str, audit: dict, participants: int) -> dict:
    if name not in SCENARIOS or not isinstance(audit, dict):
        raise ValueError('Unexpected scenario report')
    m = audit.get('manifest')
    if not isinstance(m,dict) or m.get('scenario') != name or m.get('participants') != participants:
        raise ValueError('Manifest scenario/participant mismatch')
    if m.get('split') != 'development' or m.get('no_heldout_seeds_accessed') is not True or m.get('v6_replayed_and_parity_verified') is not True:
        raise ValueError('Heldout/parity/split evidence missing')
    if not isinstance(m.get('seed_start'),int) or m['seed_start'] != 100_000 or m.get('seed_end') != m['seed_start'] + participants - 1 or m['seed_end'] >= 200_000:
        raise ValueError('Unexpected or sealed seed range')
    if m.get('session_lengths') != [20,20,15] or audit.get('synthetic_only') is not True or audit.get('human_evidence') is not False:
        raise ValueError('Unrecognized policy protocol / human-evidence label')
    means = audit.get('descriptive_means')
    comparisons = audit.get('paired_v6_minus')
    diagnostics = audit.get('v6_trigger_diagnostics')
    if not isinstance(means,dict) or not isinstance(comparisons,dict) or not isinstance(diagnostics,dict):
        raise ValueError('Missing policy means, ablations or diagnostics')
    if set(COMPARATORS) - comparisons.keys() or not all(x in means for x in ('v6',*COMPARATORS)):
        raise ValueError('Required comparisons not all reported')
    for policy, fields in means.items():
        if not isinstance(fields,dict) or any(k not in fields or type(fields[k]) not in (float,int) or not math.isfinite(fields[k]) for k in ('true_mastery','nominal_net_mastery','resource_actions')):
            raise ValueError('Malformed policy average')
        if not 0 <= fields['true_mastery'] <= 1 or fields['resource_actions'] < 0:
            raise ValueError('Impossible policy average')
    for k in ('total_triggered_recovery_actions','total_mastered_at_trigger','total_unmastered_at_trigger','total_lost_after_recorded_forgetting_at_trigger','total_unmastered_without_recorded_forgetting'):
        if type(diagnostics.get(k)) is not int or diagnostics[k] < 0:
            raise ValueError('Missing nonnegative trigger count')
    if diagnostics['total_mastered_at_trigger'] + diagnostics['total_unmastered_at_trigger'] != diagnostics['total_triggered_recovery_actions']:
        raise ValueError('Trigger accounting does not reconcile')
    if diagnostics['total_lost_after_recorded_forgetting_at_trigger'] > diagnostics['total_unmastered_at_trigger']:
        raise ValueError('Impossible forget-trigger count')
    return {'scenario':name,'manifest':m,
            'means':means,
            'paired_v6_minus': {k:positive_contrast(comparisons[k],participants) for k in COMPARATORS},
            'trigger_diagnostics':diagnostics}


def validate_realdata(report: dict) -> dict:
    """Only accept the original TRAIN/VAL-only aggregate analysis, not old Step95 split."""
    if not isinstance(report,dict) or report.get('models_selected_on_phase6_train_only') is not True or report.get('membership_exclusion_asserted') is not True:
        raise ValueError('Phase6 model selection/partition safeguards absent')
    if report.get('phase6_test_labels_evaluated') != 0 or report.get('original_phase6_test_outcomes_used_in_this_run') is not False or report.get('can_certify_clean_independent_heldout_generalization') is not False:
        raise ValueError('Unexpected heldout or independence claim')
    counts = report.get('phase6_membership_counts',{})
    if any(type(counts.get(k)) is not int or counts[k] < 1 for k in ('train','val','test')):
        raise ValueError('Missing membership counts')
    metrics = report.get('phase6_val_metrics',{})
    a,b = metrics.get('train_selected_with_forgetting'),metrics.get('train_selected_no_forgetting')
    if not isinstance(a,dict) or not isinstance(b,dict):
        raise ValueError('Missing original Phase6 VAL baselines')
    if a.get('n_students') != b.get('n_students') or a.get('n_observations') != b.get('n_observations'):
        raise ValueError('Unequal evaluation population')
    if any(type(t.get(k)) not in (int,float) or not math.isfinite(t[k]) for t in (a,b) for k in ('brier','log_loss')):
        raise ValueError('Invalid real-data predictions')
    return {'exploratory_not_confirmatory':True, 'subject':'ASSISTments mathematics',
            'n_val_students':a['n_students'], 'n_val_observations':a['n_observations'],
            'brier_forgetting':a['brier'],'brier_no_forgetting':b['brier'],
            'brier_difference':a['brier']-b['brier'],
            'log_loss_forgetting':a['log_loss'], 'log_loss_no_forgetting':b['log_loss'],
            'forecast_better_with_forgetting_in_this_development_analysis': (a['brier']<b['brier'] and a['log_loss']<b['log_loss']),
            'causal_recovery_efficacy_established':False,
            'independent_heldout_generalization_established':False,
            'source_csv_sha256':report.get('input_csv_sha256')}


def decision_from_results(scenarios: dict) -> dict:
    if set(scenarios) != set(SCENARIOS):
        raise ValueError('All five registered scenarios must be present')
    results = [scenarios[n]['paired_v6_minus']['no_recovery'] for n in SCENARIOS]
    gains = sum(x['mean_positive'] for x in results)
    all_positive = gains == len(SCENARIOS)
    descriptive_intervals_all_positive = all(x['descriptive_lower_bound_positive'] for x in results)
    return {
        'candidate':'existing V6 observation-change recovery policy',
        'development_scenarios_with_positive_mean_recovery_contrast':gains,
        'total_development_scenarios':len(SCENARIOS),
        'all_scenarios_positive_mean':all_positive,
        'all_descriptive_bootstrap_lower_bounds_positive':descriptive_intervals_all_positive,
        'conservative_predeclared_screening_pass':all_positive and descriptive_intervals_all_positive,
        'screening_only_no_confirmatory_claim':True,
        'interpretation':('Positive but still exploratory synthetic screening; require independent review and a frozen confirmatory design.'
                          if all_positive and descriptive_intervals_all_positive else
                          'NO-GO for broad V6 recovery-efficacy claim under this demanding development screening rule; preserve all negative scenarios.'),
        'independent_algorithmic_novelty_established':False,
        'real_student_intervention_effect_established':False,
    }


def build_report(*, participants: int, realdata: dict|None, root: Path = Path('.'), audits: dict|None = None) -> dict:
    if type(participants) is not int or not 3 <= participants <= 1000:
        raise ValueError('Use 3..1000 development seeds per scenario; no heldout')
    root = Path(root)
    missing = [str(root / p) for p in SOURCE_PATHS if not (root/p).is_file()]
    if missing:raise ValueError(f'Missing existing source files (no auto substitute): {missing}')
    source_digests = {p:sha(root/p) for p in SOURCE_PATHS}
    # No user-supplied arbitrary scenarios or split/seed knobs. The existing
    # independent scorer itself prohibits heldout; we recheck its output.
    if audits is None:
        from scripts import step95_v6_mechanism_audit as mechanism
        audits = {name:mechanism.audit(name,participants=participants) for name in SCENARIOS}
    verified = {name:verify_scenario(name,audits[name],participants) for name in SCENARIOS}
    decision = decision_from_results(verified)
    return {'status':'EXPLORATORY SYNTHETIC ABLATION; NOT AN EFFICACY OR NOVELTY CERTIFICATE',
            'date_context':'2026-10-31', 'source_sha256':source_digests,
            'scenarios':verified,'decision':decision,
            'real_data_context': validate_realdata(realdata) if realdata is not None else None,
            'no_heldout_access':True, 'human_participants':False,
            'original_step95_exit_criterion_completed':False,
            'original_52_step_rubric_modified':False,
            'needed_independent_signoff':True}


def render_md(report: dict) -> str:
    lines = ['# IJCAI 2027 — Existing V6 recovery ablation / go-no-go',
             '', '**DEVELOPMENT-ONLY SYNTHETIC EVIDENCE. NOT HUMAN EFFICACY.**',
             '', f"**Decision:** {report['decision']['interpretation']}", '',
             '| Scenario | V6 − no recovery (net mastery) | Descriptive interval | Wins/Ties/Losses | Mean V6 resources |',
             '|---|---:|---:|---:|---:|']
    for name in SCENARIOS:
        v = report['scenarios'][name];c = v['paired_v6_minus']['no_recovery']
        lines.append(f"| {name} | {c['mean']:+.6f} | [{c['descriptive_interval'][0]:+.6f}, {c['descriptive_interval'][1]:+.6f}] | {c['wins']}/{c['ties']}/{c['losses']} | {v['means']['v6']['resource_actions']:.3f} |")
    lines += ['', '## Independent baseline and mechanism-ablation output',
              'The JSON includes fixed, greedy, no-risk-credit and no-coverage-weight comparators, plus oracle-only post-hoc trigger diagnostics.',
              'Do not interpret simulator latent truth as an input to the controller.', '']
    x=report['real_data_context']
    if x:
        lines += ['## Separate ASSISTments forecasting result (NOT intervention effect)',
                  f"On the previously explored Phase 6 validation split ({x['n_val_students']} students, {x['n_val_observations']} observations), forgetting-minus-no-forgetting Brier = {x['brier_difference']:+.6f}.",
                  'This evidence is observational, exploratory, and on a different curriculum; it does not estimate the causal effect of recovery.', '']
    lines += ['## Scientific stop conditions',
              '- Do not claim V6 efficacy if no-recovery comparisons are nonpositive or highly uncertain.',
              '- Do not choose a new algorithm using sealed synthetic seeds (>=200000) or Phase6 test labels.',
              '- Do not claim an original IJCAI algorithm merely by combining BKT, POMCP and a trigger.',
              '- No human enrollment without content, ethics and privacy approval.',
              '- Preserve the full JSON and hashes, including unfavorable results.', '']
    return '\n'.join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--participants',type=int,default=30,help='Development seeds PER scenario, default 30')
    p.add_argument('--real-data-report',type=Path,default=None,help='Optional existing Phase6 aggregate-only JSON')
    p.add_argument('--output',type=Path,default=Path('/tmp/ijcai_nov2_v6_decision.json'))
    p.add_argument('--markdown',type=Path,default=Path('/tmp/ijcai_nov2_v6_decision.md'))
    a=p.parse_args()
    if a.output.resolve()==a.markdown.resolve():raise ValueError('Distinct output files required')
    for path in (a.output,a.markdown):
        if path.exists():raise FileExistsError(f'Refuse overwrite of prior result: {path}')
    data=None
    if a.real_data_report is not None:
        data=json.loads(a.real_data_report.read_text(encoding='utf-8'))
    report=build_report(participants=a.participants, realdata=data)
    # Do not write if execution/validation failed. Use distinct read-only
    # output paths under /tmp; original benchmark datasets are untouched.
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    a.markdown.write_text(render_md(report),encoding='utf-8')
    print('EXPLORATORY ablation report:',a.output)
    print('Decision memo:',a.markdown)
    print('Screens V6 recovery:',report['decision']['interpretation'])
    print('No data or review status modified; no human causal claims.')


if __name__=='__main__':main()
