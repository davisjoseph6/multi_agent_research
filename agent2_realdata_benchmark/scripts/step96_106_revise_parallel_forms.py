"""Editorially rewrite 16+16 assessment questions, retaining all original metadata.

Additive review-pending V2. Never replaces original drafts, fakes independent
review, or declares that pre/post forms are psychometrically equivalent.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Mapping

# Source fingerprints from user's Oct 30 generated draft manifest.
EXPECTED_ITEM_SHA256 = 'd80adfb754cd44c5e19146974cc72fcaef9da7985ab74eb2f84ffac3bd220c79'
EXPECTED_RESOURCE_SHA256 = 'b5e33fa2062853557e6fff48770f850c057ddfee2dc4468ecccaacc4ca40336b'

# Each tuple: (stem, correct answer, three *plausible but wrong* answers, explanation).
# These are NEW PROPOSED items, not reviewed research instruments. Keep forms
# matched on concept and Bloom level, but independently worded and contextualized.
# Expert review must still check difficulty and scientific correctness.
PAIRS = {
    'Utility': {
        'understand': {
            'pretest': (
                'A person prefers a guaranteed payment to a gamble with the same average cash payment. Why is this compatible with expected-utility theory?',
                'The utilities of the risky outcomes need not average to the utility of the guaranteed payment.',
                'The probabilities of the gamble must have been calculated incorrectly.',
                'Expected-utility theory always gives zero weight to possible gains.',
                'Monetary averages determine all preferences regardless of outcome utilities.',
                'Expected utility averages utilities of outcomes, rather than monetary payoffs alone.'),
            'posttest': (
                'Two people agree on a lottery’s outcome probabilities but rank it differently from a sure amount. Which explanation is compatible with expected utility?',
                'They can assign different utilities to the same monetary outcomes.',
                'Agreement on probabilities forces identical preferences over all lotteries.',
                'A sure payment is never representable by a utility function.',
                'The larger nominal prize must be preferred by both people.',
                'Utility functions can represent distinct individual preferences even when objective probabilities agree.'),
        },
        'apply': {
            'pretest': (
                'A lottery delivers utility 9 with probability 0.25 and utility 1 otherwise. What is its expected utility?',
                '3 utility units', '7 utility units', '9 utility units', '1 utility unit',
                'Multiply 9 by 0.25 and 1 by 0.75, then sum to obtain 3.'),
            'posttest': (
                'A game yields utility 10 on one out of four equally likely outcomes and utility 2 on each other outcome. What is the mean utility?',
                '4 utility units', '8 utility units', '10 utility units', '2 utility units',
                'The probability-weighted result is (10 + 2 + 2 + 2)/4 = 4.'),
        },
    },
    'Loss Aversion': {
        'understand': {
            'pretest': (
                'An identical monetary change feels stronger when described as losing money than gaining it from a reference point. Which interpretation fits loss aversion?',
                'Equal-sized losses and gains may have unequal subjective impacts.',
                'All people assign exactly twice as much weight to losses.',
                'Reference points cannot affect the subjective evaluation of money.',
                'Disliking all risky bets is the definition of loss aversion.',
                'Loss aversion is a tendency for losses relative to a reference point to loom larger than matching gains.'),
            'posttest': (
                'A person wants greater compensation to give up an owned ticket than they would pay to obtain it. What account is consistent with loss aversion?',
                'Relinquishing the ticket may be evaluated as a loss from the ownership reference state.',
                'Ownership necessarily changes the ticket’s face value at the box office.',
                'The observed difference conclusively excludes transaction costs.',
                'Loss aversion applies only when all possible outcomes are uncertain.',
                'Treating the owned ticket as the status quo can make relinquishment feel like a loss; alternative explanations remain.'),
        },
        'apply': {
            'pretest': (
                'Relative to a savings target of 100 monetary units, an outcome leaves 85. How is the outcome classified?',
                'A loss of 15 relative to the stated target', 'A gain of 85 relative to the target',
                'No change because the outcome is positive', 'A loss of 100 regardless of the outcome',
                'Subtract the reference amount: 85 − 100 = −15.'),
            'posttest': (
                'A worker expected a bonus of 60 units but actually received 75. How is this coded relative to that expectation?',
                'A gain of 15 relative to the expected bonus', 'A loss of 60 relative to the reference',
                'An unchanged outcome because both amounts are positive', 'A gain of exactly 75 beyond expectation',
                'Use the specified reference expectation: 75 − 60 = +15.'),
        },
    },
    'Anchoring': {
        'understand': {
            'pretest': (
                'A random two-digit number is displayed before a student estimates a population. The number affects estimates. What makes this an anchoring concern?',
                'An irrelevant initial number may pull judgments toward itself.',
                'The random number is therefore an accurate population statistic.',
                'Any use of numbers is mathematically incorrect.',
                'The student must have been measuring memory availability only.',
                'Anchoring can bias numerical judgments toward a prior value without informative relevance.'),
            'posttest': (
                'An applicant sees an arbitrary advertised salary before forming an independent salary estimate. Why might the estimate be biased?',
                'The visible starting figure can influence the subsequent adjustment.',
                'Any salary mentioned publicly becomes the true market median.',
                'The first figure must be chosen using an unbiased representative sample.',
                'Anchoring requires a complete absence of numerical reasoning.',
                'A potentially arbitrary initial value can act as a reference that shapes later estimates.'),
        },
        'apply': {
            'pretest': (
                'To test a suspected anchor, a researcher randomly shows high or low irrelevant numbers before the same price-estimation task. What comparison is appropriate?',
                'Compare price estimates between the randomly assigned anchor groups.',
                'Assume the high-anchor group will always be correct.',
                'Change the product quality only for the high-anchor group.',
                'Treat the displayed number as the real price without measuring estimates.',
                'Random assignment and a common task isolate the influence of the displayed initial number.'),
            'posttest': (
                'Two otherwise identical groups estimate a building’s height after seeing different arbitrary reference numbers. How should a possible anchor effect be evaluated?',
                'Test whether estimates differ systematically across the assigned reference conditions.',
                'Declare the tallest reference number to be the true building height.',
                'Conclude that any observed difference proves deliberate deception.',
                'Replace the task with different buildings for each condition.',
                'Under randomized assignment, systematic differences between estimates may indicate anchoring, subject to sampling uncertainty.'),
        },
    },
    'Sunk Cost': {
        'understand': {
            'pretest': (
                'An organizer paid a nonrefundable venue deposit. What is the correct role of that payment in choosing between future events?',
                'The past payment cannot be recovered and should not alone determine the best future option.',
                'The event must proceed simply because the deposit was large.',
                'The payment automatically makes future ticket revenue higher.',
                'Every other future cost becomes irrelevant after a deposit.',
                'A sunk payment is historical; compare the remaining costs, benefits and alternatives.'),
            'posttest': (
                'A committee argues that a cancelled prototype must be completed because earlier staff hours were expensive. Which reasoning is sound?',
                'Evaluate the expected incremental value of finishing instead of relying on irrecoverable effort.',
                'Previously spent hours guarantee future benefits if more hours are spent.',
                'Any sunk spending creates a new positive cash inflow.',
                'An opportunity cost is identical to a nonrefundable historical cost.',
                'Past irreversible effort is not itself a benefit of future continuation, though remaining alternatives matter.'),
        },
        'apply': {
            'pretest': (
                'A cancelled course already cost 400 irrecoverable units. Restarting would cost 60 more and yield 90 in additional value. What is the forward-looking net value?',
                '+30 units of incremental value', '−370 units after treating all historical costs as new',
                'Exactly 400 units because it was paid earlier', '−60 units because future benefits never count',
                'Future benefit 90 minus future cost 60 equals +30; the sunk 400 does not change this calculation.'),
            'posttest': (
                'A lab has paid 900 nonrefundable units for equipment. Completing a project costs 75 more for only 50 in expected future benefit. What is its incremental net value?',
                '−25 units; completion is not justified on the stated incremental payoff alone',
                '+825 units because the earlier purchase is an asset',
                '+50 units because future costs should be ignored',
                '−925 units because historic expenses must be counted again',
                'For the continuation decision, 50 − 75 = −25; the 900 is already sunk under the stated assumptions.'),
        },
    },
    'Framing': {
        'understand': {
            'pretest': (
                'An intervention is presented as 80% survival rather than 20% mortality, with the same underlying patients. Why might decisions change?',
                'Different descriptions can emphasize different aspects of identical outcomes.',
                'Survival and mortality automatically describe different medical treatments.',
                'The two percentages cannot refer to the same binary outcome.',
                'A framing effect requires lying about the total number of patients.',
                'The descriptions are complementary; presentation can influence judgment without changing consequences.'),
            'posttest': (
                'Two descriptions of an identical program emphasize jobs saved versus jobs lost. What best characterizes a possible framing effect?',
                'Choice may depend on the wording despite equivalent underlying consequences.',
                'The jobs must have different salaries under the two descriptions.',
                'An equivalent description always produces identical preferences for every person.',
                'Only a change in the underlying probability can alter choice.',
                'Equivalent outcome representations may lead to different preferences when the emphasized frame changes.'),
        },
        'apply': {
            'pretest': (
                'In a binary-outcome survey, 36 of 60 participants succeeded. What is the complementary failure percentage?',
                '40% failed', '36% failed', '60% failed', '24% failed',
                'Twenty-four of sixty did not succeed: 24/60 = 0.40.'),
            'posttest': (
                'A trial reports 18 failures among 90 participants, with no other outcome categories. What is the success percentage?',
                '80% succeeded', '18% succeeded', '90% succeeded', '20% succeeded',
                'There are 72 successes out of 90, so the equivalent success description is 80%.'),
        },
    },
    'Heuristics': {
        'understand': {
            'pretest': (
                'After repeatedly watching vivid burglary footage, a resident overestimates the local burglary rate. Which reasoning shortcut is plausible?',
                'Availability: memorable examples are substituted for representative frequency information.',
                'An exact computation using complete local crime records.',
                'A necessary inference that the population rate has doubled.',
                'Only a decision influenced by already-spent money.',
                'Salient examples are easily retrieved and can bias judgments about event frequency.'),
            'posttest': (
                'An investor hears about several dramatic market crashes and judges crashes more frequent than the long-run record suggests. Which shortcut fits?',
                'Availability, because striking incidents are easily recalled when frequency is estimated.',
                'A complete frequency computation from all historical observations.',
                'A requirement that the actual market crash rate has increased.',
                'An irreversible expenditure that changes future investment returns.',
                'Recent vivid crash stories can make extreme events easier to recall without changing their underlying base rate.'),
        },
        'apply': {
            'pretest': (
                'A manager remembers one dramatic product failure but needs to estimate the overall failure rate. What evidence should be used?',
                'Count failures and total relevant product trials in a representative dataset.',
                'Treat the vivid failure as every recorded trial.',
                'Ignore the denominator because memorable cases are more informative.',
                'Use the highest arbitrary number seen in a recent advertisement.',
                'A frequency estimate should use an appropriate denominator rather than one memorable incident.'),
            'posttest': (
                'A hospital worker estimates a rare complication from a single recent case. Which check reduces availability-based error?',
                'Compare observed complications with the total number of comparable procedures.',
                'Give every recent case a probability of one.',
                'Avoid consulting any historical procedure counts.',
                'Use a single unrelated patient story as the representative sample.',
                'The numerator and comparable exposure denominator provide a more defensible estimate than vivid recall.'),
        },
    },
    'Prospect Theory': {
        'understand': {
            'pretest': (
                'A person evaluates a pay raise in relation to an anticipated salary rather than only total wealth. Which principle is illustrated?',
                'The subjective coding of gains and losses depends on a reference point.',
                'Objective probabilities must equal one-half in every prospect.',
                'Reference points can never depend on expectations.',
                'Prospect theory requires monetary outcomes to be ignored.',
                'The same nominal outcome can be coded differently depending on the comparison baseline.'),
            'posttest': (
                'An investor describes a portfolio ending at 110 as disappointing after expecting 120 but satisfying after expecting 100. What accounts for the difference?',
                'The outcome changes sign relative to the chosen expectation reference.',
                'The portfolio’s final value must have changed between descriptions.',
                'Reference expectations are excluded from prospect theory.',
                'The value of any outcome is independent of its reference level.',
                'With a final value fixed at 110, expectations of 120 and 100 yield a relative loss and a relative gain respectively.'),
        },
        'apply': {
            'pretest': (
                'A share closes at 45 while the decision maker uses 50 as a reference. What is the reference-relative change?',
                'A 5-unit loss', 'A 45-unit gain', 'An unchanged outcome', 'A 50-unit profit',
                'Subtract 50 from 45 to obtain a −5 change.'),
            'posttest': (
                'A bonus of 115 units is evaluated against a promised 100-unit baseline. What reference-relative change is coded?',
                'A 15-unit gain', 'A 100-unit loss', 'A 115-unit disappointment', 'No change from the baseline',
                'The stated difference is 115 − 100 = +15.'),
        },
    },
    'Nudge Theory': {
        'understand': {
            'pretest': (
                'A website preselects an optional reminder but allows immediate cancellation without penalty. Which feature makes this a plausible nudge?',
                'The interface guides choice while preserving an accessible alternative.',
                'The alternative option is legally banned.',
                'The user must pay an unavoidable fee to refuse the reminder.',
                'All participants are compelled to select the preselected option.',
                'A reversible default changes choice architecture without eliminating meaningful opt-out.'),
            'posttest': (
                'A cafeteria places healthier items at eye level while selling the same full menu. Why may this count as choice architecture?',
                'The presentation may influence selection while keeping the original options available.',
                'Customers are prohibited from purchasing other menu items.',
                'The arrangement mathematically changes the calories of every food.',
                'The intervention always improves well-being for every individual.',
                'Salience and placement can affect choices without removing options; benefits must still be assessed.'),
        },
        'apply': {
            'pretest': (
                'A savings form preselects an optional contribution rate. What must be verified before describing the design as noncoercive?',
                'A clear, low-friction ability to change or decline the contribution.',
                'A hidden opt-out button available only after payment.',
                'A mandatory contribution with no exit path.',
                'A penalty for every person who changes the default.',
                'Preserving meaningful choice requires a transparent and realistically accessible alternative.'),
            'posttest': (
                'A school proposes an automatic but reversible email reminder. Which implementation best preserves student autonomy?',
                'Explain the default and provide a visible, simple way to unsubscribe.',
                'Send messages regardless of explicit objections.',
                'Hide all notification settings from recipients.',
                'Treat silence as permission to remove access to services.',
                'Transparency and easy reversal preserve choice; privacy and consent requirements remain.'),
        },
    },
}

FORMS = ('pretest','posttest')
BLOOM = ('understand','apply')


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> tuple[tuple[str, ...], list[dict[str,str]]]:
    with path.open(encoding='utf-8-sig',newline='') as fh:
        r=csv.DictReader(fh)
        if not r.fieldnames:
            raise ValueError(f'CSV header missing: {path}')
        fields=tuple(r.fieldnames)
        rows=list(r)
    if any(None in row for row in rows):
        raise ValueError('Unexpected CSV column')
    return fields,rows


def revise(items: list[dict[str, str]]) -> tuple[list[dict[str,str]],list[str]]:
    if len(items)!=95 or len({r.get('item_id') for r in items})!=95:
        raise ValueError('Invalid item count or duplicate IDs')
    expected={(concept,bloom,form) for concept in PAIRS for bloom in BLOOM for form in FORMS}
    actual=Counter((r.get('concept'),r.get('bloom'),r.get('form')) for r in items if r.get('form') in FORMS)
    if set(actual)!=expected or any(actual[k]!=1 for k in expected):
        raise ValueError('Assessment blueprint differs from expected 8 concepts × 2 matching Bloom levels × 2 forms')
    revised=[]; modified=[]
    for original in items:
        row=dict(original)
        if row['form'] in FORMS:
            if (row.get('review_decision') != 'pending' or row.get('reviewer_record','').strip() or row.get('review_date','').strip()):
                raise ValueError('Cannot rewrite a reviewed/approved item')
            prompt,correct,wrong1,wrong2,wrong3,rationale=PAIRS[row['concept']][row['bloom']][row['form']]
            # Keep original keyed option letter and all non-content metadata;
            # change only the substantive assessment text and rationale.
            key=row.get('correct_option_id')
            if key not in 'ABCD' or len(key)!=1:
                raise ValueError('Missing or invalid original answer key')
            row['prompt']=prompt
            row['rationale']=rationale
            row['option_'+key]=correct
            wrong_iter=iter((wrong1,wrong2,wrong3))
            for letter in 'ABCD':
                if letter!=key:
                    row['option_'+letter]=next(wrong_iter)
            modified.append(row['item_id'])
        revised.append(row)
    if len(modified)!=32:
        raise AssertionError('Must revise exactly 32 assessment items')
    return revised,modified


def run(items_path:Path,resources_path:Path,output:Path,*,
        expected_item_sha256=EXPECTED_ITEM_SHA256,
        expected_resource_sha256=EXPECTED_RESOURCE_SHA256) -> dict:
    if digest(items_path)!=expected_item_sha256 or digest(resources_path)!=expected_resource_sha256:
        raise ValueError('Source draft hashes differ; refuse to rewrite an unrecognized or edited bank')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    fields,items=read_rows(items_path)
    resource_fields,resources=read_rows(resources_path)
    revised,modified=revise(items)
    from scripts.step96_106_semantic_quality_gate import assess
    before=assess(items,resources)
    after=assess(revised,resources)
    # A substantive correction cannot introduce new high-risk or blocking flags.
    def risk(report):
        return sum(v for k,v in report['severity_counts'].items() if k in ('high','blocking'))
    if risk(after)>=risk(before):
        raise ValueError('Revision does not reduce flagged high/blocking risks')
    if after['review_pending_count']!=127:
        raise AssertionError('Independent review gates must remain outstanding')
    output.mkdir(parents=True)
    items_target=output/'authored_items_PENDING_REVIEW.csv'
    resources_target=output/'authored_resources_PENDING_REVIEW.csv'
    with items_target.open('w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(revised)
    shutil.copyfile(resources_path,resources_target)
    manifest={
       'status':'DRAFT; NOT EXPERT-APPROVED; NOT VALIDATED FOR HUMAN STUDY',
       'original_items_sha256':digest(items_path),
       'original_resources_sha256':digest(resources_path),
       'new_items_sha256':digest(items_target),
       'new_resources_sha256':digest(resources_target),
       'unchanged_resource_bytes':digest(resources_target)==digest(resources_path),
       'revised_item_ids':modified,
       'revised_count':len(modified),
       'review_pending_count':after['review_pending_count'],
       'before_severity_counts':before['severity_counts'],
       'after_severity_counts':after['severity_counts'],
       'before_flag_counts':before['flag_counts'],
       'after_flag_counts':after['flag_counts'],
       'limits':['Mechanically distinct assessments are not psychometrically parallel.',
                 'No expert factual or answer-key review has occurred.',
                 'Bloom create remains multiple-choice and therefore unvalidated.',
                 'Practice resources, practice answer sets and DROP_2 content are unchanged.',
                 'No original source or reviewed bank is overwritten.'],
    }
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--items',type=Path,default=Path('docs/nov2_content_review_drafts/authored_items_PENDING_REVIEW.csv'))
    p.add_argument('--resources',type=Path,default=Path('docs/nov2_content_review_drafts/authored_resources_PENDING_REVIEW.csv'))
    p.add_argument('--output',type=Path,default=Path('docs/nov2_assessment_revisions_v2_PENDING_REVIEW'))
    a=p.parse_args()
    print(json.dumps(run(a.items,a.resources,a.output),indent=2,ensure_ascii=False))

if __name__=='__main__': main()
