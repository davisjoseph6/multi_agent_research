"""Generate REVIEW-PENDING behavioral-economics content into a separate directory.

Never overwrite canonical source slots or claim scholarly/psychometric review.
The authoring prompts are proposed original teaching questions, not adapted
verbatim from copyrighted sources, and need expert review.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

CONCEPTS = ('Utility','Loss Aversion','Anchoring','Sunk Cost','Framing', 'Heuristics','Prospect Theory','Nudge Theory')
BLOOM = ('remember','understand','apply','analyze','evaluate','create')
ACTIONS = ('CONCEPT_SUMMARY','DROP_2','WORKED_EXAMPLE','SOCRATIC_HINT')
FORMS = {'pretest':16,'posttest':16,'practice':55,'recovery_drop2':8}
# Fully qualified, verified primary source references; references are
# pedagogical provenance, not proof that each question is correct.
SOURCES={
 'Utility':'von Neumann and Morgenstern, Theory of Games and Economic Behavior (1944), Princeton University Press; expected-utility framework',
 'Loss Aversion':'Tversky and Kahneman (1991), Loss Aversion in Riskless Choice, https://doi.org/10.2307/2937956',
 'Anchoring':'Tversky and Kahneman (1974), Judgment under Uncertainty, https://doi.org/10.1126/science.185.4157.1124',
 'Sunk Cost':'Arkes and Blumer (1985), The Psychology of Sunk Cost, https://doi.org/10.1016/0749-5978(85)90049-4',
 'Framing':'Tversky and Kahneman (1981), The Framing of Decisions and the Psychology of Choice, https://doi.org/10.1126/science.7455683',
 'Heuristics':'Tversky and Kahneman (1974), Judgment under Uncertainty, https://doi.org/10.1126/science.185.4157.1124',
 'Prospect Theory':'Kahneman and Tversky (1979), Prospect Theory, https://doi.org/10.2307/1914185',
 'Nudge Theory':'Thaler and Sunstein (2008), Nudge: Improving Decisions About Health, Wealth, and Happiness, Yale University Press, ISBN 9780300122237',
}
# Each row has *two separately authored applications* plus one correct answer,
# three concept-specific misconceptions, and one explanation. All are drafts.
# For Bloom "create" these MCQs evaluate selection of a good design, and do
# NOT assess open-ended creative production. This construct gap is documented.
C = {
 'Utility':{
  'remember':(
   'In a simple expected-utility model, what is the value of a lottery with outcomes indexed by i?',
   'A decision scientist asks how a von Neumann–Morgenstern expected-utility agent ranks lotteries. Which expression applies?',
   'The sum of each outcome utility multiplied by its probability.',
   'The largest possible monetary payoff only.','The average payoff squared.','The lowest outcome utility regardless of probability.',
   'Expected utility is probability-weighted utility, not necessarily expected money.'),
  'understand':(
   'Two agents value the same risky cash payoff differently. Which explanation fits expected-utility theory?',
   'A student asks why a guaranteed amount may be preferred to a gamble with the same expected money. Which explanation fits?',
   'Utilities can represent different preferences over risky outcomes.',
   'Both agents must maximize expected cash.','Probability has no effect on preferences.','Any preference for certainty proves probability neglect.',
   'Expected monetary payoff and expected utility can rank lotteries differently.'),
  'apply':(
   'An agent has U($0)=0 and U($100)=10. What is expected utility of a 50%-50% lottery over those outcomes?',
   'A coin pays an outcome of utility 2 on tails and utility 8 on heads. What is its expected utility?',
   '5', '10','2','8',
   'Weight the stated endpoint utilities by probability; both examples evaluate to 5.'),
  'analyze':(
   'Lottery A gives utility 6 for sure. Lottery B gives utility 10 with probability 0.5 and utility 0 otherwise. Which is preferred under expected utility?',
   'An agent compares certain utility 6 with a fair coin giving utilities 0 or 10. Which calculation decides?',
   'The certain option: 6 exceeds the gamble’s expected utility of 5.',
   'The gamble because 10 is its highest payoff.','Both options because probabilities cancel.','Neither can be compared without monetary units.',
   'The expected utility of the equal-probability gamble is 5.'),
  'evaluate':(
   'A report claims a choice is irrational solely because its expected cash reward is lower. What is the strongest critique?',
   'A reviewer says risk aversion proves calculation error whenever expected money is higher for a lottery. Which response is defensible?',
   'Expected utility depends on preferences over outcomes, not just expected cash.',
   'Expected cash must be maximized in all decision models.','Utility always equals cash.','Risk preferences never affect a comparison.',
   'Without specifying utility, expected-money maximization is not an appropriate universal benchmark.'),
  'create':(
   'Which design best tests whether two learners have different utility curvature?',
   'A researcher is building a classroom activity to elicit risk preferences. Which design is most informative?',
   'Offer several choices between sure amounts and probability-defined lotteries, with consistent stakes.',
   'Ask only for the largest imaginable prize.','Show an unlabeled picture of a coin.','Ask whether the learner likes mathematics.',
   'Multiple documented sure-versus-risky tradeoffs can help characterize preferences, subject to experimental limitations.'),
 },
 'Loss Aversion':{
  'remember':(
   'Which statement defines loss aversion in reference-dependent choice?',
   'A participant compares a $20 gain to a $20 loss relative to a reference point. What is loss aversion?',
   'A loss can have greater psychological impact than an equal-sized gain.',
   'All losses have exactly zero subjective value.','The decision maker always dislikes every gamble.','Only absolute wealth matters, never a reference point.',
   'Loss aversion compares the subjective impacts of gains and losses around a reference point.'),
  'understand':(
   'Why might someone demand more to give up a mug they own than they would pay to acquire it?',
   'A holder values relinquishing a small entitlement differently from obtaining the same entitlement. Which account fits?',
   'Giving it up may be coded as a loss relative to ownership.',
   'Ownership makes the mug objectively more useful to everyone.','The market price must have increased.','The person must be unable to understand money.',
   'Reference-dependent loss aversion is one possible mechanism; other explanations remain possible.'),
  'apply':(
   'A commuter views a $10 fee as a loss but a $10 discount as a gain. Which manipulation changes reference dependence?',
   'A subscription advertises either a $5 surcharge or the loss of a $5 discount. Which factor should be held fixed to test loss aversion?',
   'Keep final monetary outcomes equivalent while changing the reference description.',
   'Change both the money and the product quality.','Remove the reference point from the analysis.','Assume all participants assign identical utilities.',
   'Isolate reference framing while holding actual outcomes constant.'),
  'analyze':(
   'A seller asks $40 to surrender a ticket but would pay $25 to buy the identical ticket. What can be concluded?',
   'Buying and selling valuations differ for an identical object. How should a researcher interpret the difference?',
   'It is consistent with a reference-dependent valuation gap but does not alone prove its cause.',
   'It mathematically proves all humans are loss averse.','It shows the ticket changed its intrinsic quality.','It proves risk neutrality.',
   'The gap is suggestive but confounds such as transaction costs must be considered.'),
  'evaluate':(
   'An article calls all dislike of risk loss aversion. Which criticism is most accurate?',
   'A student equates loss aversion with concave utility over final wealth. What needs correction?',
   'Loss aversion concerns asymmetric valuation of losses and gains relative to a reference point.',
   'Loss aversion requires all choices to be risky.','Reference points are irrelevant.','Loss aversion is identical to mathematical risk aversion.',
   'Risk aversion and loss aversion are conceptually distinct, although they may coexist.'),
  'create':(
   'Which study design best isolates the role of ownership as a reference point?',
   'A researcher wants to test a loss-aversion account of trading reluctance. Which protocol is strongest?',
   'Randomize initial ownership, hold incentives constant, and compare willingness to give up versus acquire.',
   'Interview only owners who refuse all trades.','Alter product quality for each group.','Treat initial ownership as an objective price increase.',
   'Randomization and controlled incentives help isolate reference-dependent ownership effects.'),
 },
 'Anchoring':{
  'remember':(
   'What is anchoring in numerical judgment?',
   'An arbitrary opening number influences a later estimate. Which cognitive bias is being described?',
   'An initial value can pull a later estimate toward it.',
   'The final estimate must equal the first number.','Only the true population mean matters.','Numerical values can never affect judgment.',
   'Anchoring is an influence of a salient starting value on subsequent judgment.'),
  'understand':(
   'Why could two groups estimate different house prices after seeing different starting prices?',
   'A survey gives half the respondents a high example number and half a low one. Why could answers diverge?',
   'The starting values can influence later estimates even when not diagnostic.',
   'All houses have different physical sizes across groups.','The high anchor reveals the correct answer.','Random assignment guarantees identical individual answers.',
   'A randomized anchor can affect numerical judgment even without genuine informational content.'),
  'apply':(
   'A salary negotiation opens at an unusually high figure. Which precaution reduces anchoring?',
   'A buyer sees a large suggested retail price before evaluating a product. What is a useful corrective action?',
   'Establish an independent evidence-based range before considering the opening number.',
   'Accept the opening number as a factual estimate.','Multiply the opening number by two.','Ignore all external price evidence.',
   'Independent benchmarks may reduce reliance on an arbitrary anchor.'),
  'analyze':(
   'One group sees the number 10 and guesses 32; another sees 90 and guesses 65 on the same task. Which interpretation is safest?',
   'Two randomized groups give different numerical answers after unequal prompts. What follows?',
   'The difference is consistent with an anchoring effect; design and uncertainty still require examination.',
   'It proves the estimates are both objectively correct.','The answers demonstrate loss aversion instead.','It is impossible to test numerical anchoring experimentally.',
   'Anchor manipulation and outcome differences support a hypothesis only within a valid design.'),
  'evaluate':(
   'A paper reports an anchor effect but compares experts with novices given different numbers. What is the key concern?',
   'An investigator attributes all estimate differences to anchors without randomizing the first number. Why is this weak?',
   'Group differences can confound the estimated anchor effect.',
   'Numerical prompts cannot be causal factors.','Anchoring always disappears for experts.','The reported effect must be perfectly measured.',
   'Without comparable groups, other factors can explain differences.'),
  'create':(
   'Which classroom experiment most cleanly tests arbitrary anchoring?',
   'Choose a study that isolates starting-number influence on an unrelated factual estimate.',
   'Randomly assign high or low irrelevant numbers, ask the same estimate, then compare groups.',
   'Let participants choose their anchor and outcome freely.','Give one group more factual evidence.','Show all students the same high number.',
   'Randomization and a common target estimate allow a direct comparison of anchor conditions.'),
 },
 'Sunk Cost':{
  'remember':(
   'Which cost is sunk when deciding whether to continue a project?',
   'A team spent money last month that it cannot recover. How is that past expenditure classified?',
   'A past, irrecoverable expenditure.',
   'Any cost that can still be refunded.','Only future variable spending.','A benefit expected from completing the project.',
   'A sunk cost has already been incurred and cannot be recovered by the current choice.'),
  'understand':(
   'Why should the original ticket purchase not decide whether to attend an unpleasant concert?',
   'A nonrefundable fee has already been paid. Why is it usually irrelevant to the attend-or-skip choice?',
   'The payment is unchanged by the future choice; compare future costs and benefits.',
   'The payment can automatically be recovered by attendance.','Past expenses are future benefits.','Attendance must be chosen to honor any expenditure.',
   'Sunk costs are fixed across the remaining options.'),
  'apply':(
   'A company can spend another $300 for a project expected to return $200 from now on. Past spending is unrecoverable. What is the forward-looking decision?',
   'A student can pay $80 more for a course expected to deliver $40 of remaining value. Registration fees are lost either way. What should guide continuation?',
   'Do not continue solely to justify the past spending; incremental costs exceed benefits.',
   'Continue because substantial fees were paid earlier.','Pretend past expenditures can still be refunded.','Ignore the future $300 or $80 cost.',
   'Under the stated assumptions, remaining net value is negative.'),
  'analyze':(
   'Two teams have identical future project returns, but one has spent more in the past. Should optimal forward-looking decisions differ solely because of that spending?',
   'An investor doubles down after a poor return because the purchase price was high. Which reasoning error is possible?',
   'No: irrecoverable past spending alone does not change future incremental value.',
   'Yes: larger historic spending always raises future returns.','Yes: losses are mathematically reversed by reinvesting.','No comparison of future options is needed.',
   'Past sunk spending does not enter a forward-looking incremental decision.'),
  'evaluate':(
   'A consultant recommends continuing because abandoning would “waste” the budget already spent. What should a reviewer ask?',
   'A committee argues that a failed pilot deserves expansion because it consumed much staff time. Which objection is strongest?',
   'Compare expected future incremental benefits with future costs, excluding irrecoverable spending.',
   'Require more spending to make the historic total larger.','Assume future outcomes must be better after more investment.','Count the same historical cost as a new benefit.',
   'Future opportunity costs and recoverable assets may matter, unlike irrecoverable spending.'),
  'create':(
   'Which decision memo best guards against sunk-cost escalation?',
   'A project board wants a process that prevents past investments from dominating renewal decisions. Which design works best?',
   'Require a fresh forecast of future costs and benefits, with sunk spending reported separately.',
   'Rank projects by money already lost.','Require continuation whenever at least one invoice was paid.','Prohibit considering any future opportunity cost.',
   'Separating historical accounting from incremental decisions counters sunk-cost reasoning.'),
 },
 'Framing':{
  'remember':(
   'What is a framing effect in choice?',
   'The same outcome is described as a survival rate or as a mortality rate. What kind of effect may follow?',
   'Different descriptions of equivalent outcomes can change preferences.',
   'Any wording change must alter the objective probabilities.','Framing requires inaccurate facts.','No decision can have multiple equivalent descriptions.',
   'Equivalent descriptions can elicit different choices despite unchanged consequences.'),
  'understand':(
   'A treatment is described as 90% survival instead of 10% mortality. Why could preferences differ?',
   'A benefit is described as avoiding a loss instead of receiving a gain. What might change?',
   'The description emphasizes different aspects of the same consequences.',
   'The physical treatment is automatically different.','The probabilities must sum to more than one.','Every patient will interpret both frames identically.',
   'Presentation can alter attention and evaluation while outcomes remain unchanged.'),
  'apply':(
   'Which pair of descriptions is mathematically equivalent, assuming a single binary outcome?',
   'A risk dashboard wants equivalent positive and negative descriptions. Which pair qualifies?',
   '80% success and 20% failure.',
   '80% success and 80% failure.','80% success and 40% failure.','80 successes and 80 failures out of 100.',
   'For complementary binary outcomes, success and failure percentages sum to 100%.'),
  'analyze':(
   'Group A sees “70 of 100 survive”; group B sees “30 of 100 die.” Choices differ. What is necessary to attribute the difference to framing?',
   'Two messages state the same binary risk with opposite wording. What should a comparative study control?',
   'Confirm equivalent outcomes and comparable assignment conditions.',
   'Assume every preference difference is logically irrational.','Use different underlying risk levels for each group.','Hide all numerical outcomes from participants.',
   'Causal framing evidence requires controlled equivalence and assignment.'),
  'evaluate':(
   'A campaign advertises a 95% success rate but omits the 5% failure rate. What is the strongest transparency recommendation?',
   'An educator presents only lives-saved counts for a high-stakes choice. What improves fairness?',
   'Show both complementary frames and the underlying denominator.',
   'Conceal the denominator to simplify perception.','Change the actual base rate during explanation.','Claim that the positive frame is the only mathematically valid one.',
   'Transparent risk communication reduces selective presentation.'),
  'create':(
   'Which survey design tests a pure wording frame rather than an outcome change?',
   'A research group wants to compare gain and loss descriptions of an identical program. Which design is strongest?',
   'Randomly assign mathematically equivalent descriptions while holding consequences constant.',
   'Alter both the treatment and the description.','Allow respondents to self-select based on preferences.','Give a different denominator to each group.',
   'A controlled randomized frame comparison isolates presentation effects.'),
 },
 'Heuristics':{
  'remember':(
   'What is the availability heuristic?',
   'A judge estimates frequency based on how easily examples come to mind. Which heuristic is involved?',
   'Assessing frequency or likelihood using ease of recall.',
   'Always calculating exact base rates.','Ignoring all personal experiences.','Selecting the largest numeric anchor only.',
   'Availability substitutes ease of retrieving examples for a more systematic frequency estimate.'),
  'understand':(
   'After hearing several airplane-crash stories, someone overestimates crash frequency. Why might this happen?',
   'A vivid recent event dominates a risk estimate despite stable statistics. Which mechanism is plausible?',
   'Memorable examples become easy to recall and can bias perceived frequency.',
   'The actual base rate must have doubled.','A vivid event proves every event has equal probability.','This necessarily shows the sunk-cost effect.',
   'Memory accessibility can distort frequency judgments without changing real event rates.'),
  'apply':(
   'A manager judges candidate skill from one memorable success while ignoring hundreds of outcomes. What is a useful correction?',
   'An analyst remembers one fraud case and declares all customers risky. What should they consult?',
   'Use representative data and base rates rather than only vivid examples.',
   'Discard all statistical evidence.','Treat the vivid case as the full sample.','Switch to an arbitrary unrelated anchor.',
   'Base-rate evidence counters unrepresentative availability-based impressions.'),
  'analyze':(
   'A sample of 4 people matches a stereotype but the base rate is low. What error is possible?',
   'An interviewer judges probability by resemblance to a prototype, overlooking prevalence. Which heuristic is implicated?',
   'Representativeness with insufficient attention to prior prevalence.',
   'Exact Bayesian updating of all available evidence.','The endowment effect as a necessary explanation.','A pure sunk-cost decision.',
   'Similarity to a prototype is not identical to posterior probability.'),
  'evaluate':(
   'A report labels every fast judgment irrational. What is the best critique?',
   'A training guide says heuristics are always harmful. How should it be revised?',
   'Heuristics can be efficient and useful, but their biases depend on context and task.',
   'Heuristics are always optimal by definition.','All judgments must be consciously calculated.','Biases never occur when people use shortcuts.',
   'The 1974 review describes economical rules that can produce systematic errors.'),
  'create':(
   'Which evaluation procedure most directly checks whether an availability shortcut is misleading?',
   'A policymaker wants a safeguard against memorable anecdotes. Which decision support is strongest?',
   'Present measured event frequencies beside anecdotal cases and record both sources.',
   'Present only the most dramatic case.','Remove every base-rate denominator.','Select the first available numerical anchor.',
   'Showing representative frequencies alongside salient cases makes the possible bias auditable.'),
 },
 'Prospect Theory':{
  'remember':(
   'In classic prospect theory, outcomes are commonly evaluated relative to what?',
   'A decision model represents gains and losses rather than only final wealth. Which reference is central?',
   'A reference point against which gains and losses are defined.',
   'Only the highest future possible wealth.','An identical utility number for every outcome.','A fixed probability of exactly 50% for every prospect.',
   'Prospect theory models value in terms of gains and losses relative to a reference state.'),
  'understand':(
   'Why can the same change in final wealth feel different depending on the starting reference?',
   'A person evaluates a bonus relative to an expected salary. Which prospect-theoretic idea explains this?',
   'Outcomes may be coded as gains or losses relative to an expected or current level.',
   'Final assets alone determine subjective value in every model.','Reference points can never change.','Probabilities are always irrelevant.',
   'Reference dependence changes the coding of a given monetary outcome.'),
  'apply':(
   'An outcome of $90 is compared against a $100 reference point. How is it coded in prospect theory?',
   'A balance rises from a reference level of $70 to $90. How is this change coded?',
   'A loss or gain determined by subtraction from the relevant reference point.',
   'An outcome whose sign cannot depend on a reference point.','Always a gain, regardless of baseline.','A result that must be evaluated by expected money alone.',
   'The key operation is outcome minus reference; it is -$10 in the first case and +$20 in the second.'),
  'analyze':(
   'Two probabilities are presented with different decision weights. Which claim is consistent with prospect theory?',
   'A model replaces objective probabilities with psychological weights in evaluating outcomes. How does this differ from expected utility?',
   'Decision weights can differ from objective probabilities.',
   'Every psychological weight equals its objective probability by definition.','Reference dependence is absent from prospect theory.','No risky prospects can be compared.',
   'The 1979 prospect-theory model uses decision weights rather than unmodified probabilities.'),
  'evaluate':(
   'An article says prospect theory predicts that every person always seeks risk for losses. What is a sound response?',
   'A lecture presents risk-seeking for losses as a universal mathematical law. How should this be qualified?',
   'It describes an empirically observed tendency under some conditions, not a universal rule.',
   'Prospect theory contains no risk preferences.','All probabilities are treated equally in every case.','Losses cannot influence decisions.',
   'Observed risk patterns depend on reference points, probability weighting, task and individual differences.'),
  'create':(
   'Which instrument best distinguishes a reference-dependent model from an expected-utility model?',
   'A researcher wants to test whether presentation around reference points changes choices. Which protocol is useful?',
   'Elicit choices over matched risky prospects under explicitly varied reference descriptions.',
   'Ask a single respondent whether they know the theory’s name.','Use only hypothetical outcomes with no stated probabilities.','Change all objective probabilities between conditions without recording them.',
   'Matched risky prospects with controlled reference manipulations can probe explanatory differences.'),
 },
 'Nudge Theory':{
  'remember':(
   'Which feature characterizes a nudge in choice architecture?',
   'A form changes its default selection but still lets a person opt out. What is this often called?',
   'Changing the decision environment while preserving meaningful choice.',
   'Banning every alternative choice.','Imposing an unavoidable punishment for refusal.','Replacing all options with a single mandatory action.',
   'The original nudge framework emphasizes choice architecture without eliminating alternatives.'),
  'understand':(
   'Why might displaying healthy food first influence selection without restricting the menu?',
   'A website makes one optional savings setting more salient. How can this influence behavior?',
   'Salience and default presentation can affect choices while options remain available.',
   'The arrangement changes the nutritional content of every item.','Every user must always accept the first option.','No human can notice interface defaults.',
   'Choice presentation can influence attention and effort; effect size requires empirical verification.'),
  'apply':(
   'A pension form preselects a voluntary savings rate but includes an easy opt-out. Which feature should a designer verify?',
   'A university offers an optional reminder for registration deadlines. What makes it a plausible nudge rather than compulsion?',
   'Opting out is genuinely easy and the intervention is transparent.',
   'Participation is legally mandatory without disclosure.','Nonparticipants are denied all services.','The reminder changes actual deadlines without notice.',
   'Freedom of choice and transparency are important in evaluating default or reminder designs.'),
  'analyze':(
   'An institution raises the cost of refusing a default to an unaffordable amount. Is the intervention clearly a benign nudge?',
   'A planner hides opt-out information when implementing an automatic choice. What concern arises?',
   'No: substantial barriers to refusal undermine meaningful choice.',
   'Yes: any default is automatically noncoercive.','Yes: no ethical analysis is relevant.','Only the interface color determines whether an intervention is a nudge.',
   'Choice preservation must be meaningful, not merely theoretical.'),
  'evaluate':(
   'A savings app claims its nudge works because sign-ups rose, without measuring welfare or consent. What is missing?',
   'A university judges a default enrollment purely by clicks. What further evaluation is warranted?',
   'Assess informed autonomy, heterogeneous effects and outcomes that matter to users.',
   'Any increase in clicks proves users are better off.','Remove the possibility of opting out to obtain larger effects.','Assume all students want identical outcomes.',
   'Behavior change alone is not sufficient evidence of welfare improvement or ethical acceptability.'),
  'create':(
   'Which design best evaluates an ethical default for library reminder subscriptions?',
   'An administrator wants to test an opt-out reminder feature. Which evaluation is strongest?',
   'Randomize a transparent, reversible default and measure meaningful outcomes and opt-outs.',
   'Hide the default change from all users.','Forbid the alternative choice.','Measure only implementation cost and ignore user outcomes.',
   'A transparent controlled design can test efficacy while preserving choice and documenting tradeoffs.'),
 },
}

# Concise but subject-specific intervention resource concepts, each paired
# with the same exact citation as the corresponding question bank.
LESSONS = {
 'Utility': ('A lottery is evaluated by the sum of outcome utilities weighted by their probabilities. Utility need not equal cash.', 'If U(0)=0 and U(100)=10, a fair coin gives expected utility 5. Compare that with the utility of a sure outcome.', 'If one prize has higher cash value, does that prove its expected utility is higher? What additional information is needed?'),
 'Loss Aversion': ('Loss aversion assigns a larger impact to a loss than an equal-sized gain relative to a reference point.', 'A person may require more compensation to surrender an owned item than they would pay to acquire it; examine reference points and alternative explanations.', 'If buying and selling valuations differ, which comparison would distinguish loss aversion from transaction costs?'),
 'Anchoring': ('An initial number can influence later estimates even when it carries little genuine evidence.', 'Randomly show a high or low irrelevant number before asking the same factual estimate. Compare the groups.', 'Before hearing a suggested price, what independent benchmark could you construct?'),
 'Sunk Cost': ('A sunk cost is unrecoverable past spending. Compare remaining future benefits with remaining future costs.', 'A project already cost $900. Completing it costs $300 and offers $200 in expected future value. Continuing has a negative incremental payoff.', 'If the past payment cannot be refunded, how can it change the remaining options?'),
 'Framing': ('Equivalent outcomes can be described in different ways, such as survival versus mortality, and these frames may affect preference.', 'Describe a binary outcome as 80% survival or 20% mortality; hold outcomes constant and compare responses.', 'When two messages use different words, how will you check that they communicate the same probabilities?'),
 'Heuristics': ('Availability uses ease of recall to judge frequency; representativeness uses resemblance to a prototype; anchoring uses a starting value.', 'When a vivid anecdote suggests a risk is common, compare it against the actual measured event frequency.', 'Is your estimate based on a representative denominator or merely on the first example that came to mind?'),
 'Prospect Theory': ('Classic prospect theory evaluates gains and losses relative to reference points, with subjective decision weights for probabilities.', 'A $90 result is a $10 loss relative to $100 but a $20 gain relative to $70. Keep the outcome fixed while comparing references.', 'Is the person responding to final wealth, a change from a baseline, or a probability weighted psychologically?'),
 'Nudge Theory': ('Choice architecture changes how options are presented while retaining genuine alternatives; transparency and ethics matter.', 'Make an optional reminder the reversible default, provide a clear opt-out, and assess useful outcomes instead of just clicks.', 'Can the user readily refuse the default? How would you learn whether the intervention benefits them?'),
}

ITEM_FIELDS = ('item_id','form','concept','bloom','learning_objective','prompt','option_A','option_B','option_C','option_D','correct_option_id','rationale','source_citation','review_decision','reviewer_record','review_date','difficulty_estimate')
RESOURCE_FIELDS = ('resource_id','concept','action','learning_objective','resource_text','source_citation','review_decision','reviewer_record','review_date')

def load_rows(path, expected_columns):
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise ValueError(f'Unexpected schema for {path}: {reader.fieldnames!r}')
        return list(reader)

def write_rows(path,fields,rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)

def author_item(row, count):
    if row['concept'] not in C or row['bloom'] not in C[row['concept']]:
        raise ValueError(f'Unsupported concept or Bloom: {row["item_id"]}')
    first,second,correct,*tail=C[row['concept']][row['bloom']]
    distractors=tail[:3]; rationale=tail[3]
    prompt = (first,second)[count % 2]
    # For unexpected 3+ duplicates in one concept/Bloom, be transparent about
    # the expanded variant; don't pretend these are independently designed.
    if count >= 2:
        prompt = f'Additional review variant {count+1}: {prompt} Explain the decision using the stated assumptions.'
    choices=[correct]+distractors
    # Deterministic answer-key positions; no randomized outcomes or human data.
    rotation=int(sha256(row['item_id'].encode()).hexdigest()[:6],16)%len(choices)
    choices=choices[rotation:]+choices[:rotation]
    keyed='ABCD'[choices.index(correct)]
    out=dict(row)
    out['learning_objective']=f'{row["bloom"].capitalize()}: correctly reason about {row["concept"]} in a decision-making context.'
    out['prompt']=prompt
    out.update({f'option_{key}':choices[i] for i,key in enumerate('ABCD')})
    if row['form']=='recovery_drop2':
        # Exactly two choices: keep correct plus one misconception; index
        # positions are preserved, all others are blank.
        wrong=next(key for key in 'ABCD' if key!=keyed)
        for letter in 'ABCD':
            if letter not in (wrong,keyed): out[f'option_{letter}']=''
    out['correct_option_id']=keyed
    out['rationale']=rationale
    out['source_citation']=SOURCES[row['concept']]
    out['review_decision']='pending'
    out['reviewer_record']=''
    out['review_date']=''
    # Author's preliminary difficulty judgement; NOT an empirical estimate.
    out['difficulty_estimate']=str({'remember':.25,'understand':.35,'apply':.50,'analyze':.60,'evaluate':.70,'create':.80}[row['bloom']])
    return out

def author_resource(row):
    concept,action=row['concept'],row['action']
    if concept not in LESSONS or action not in ACTIONS: raise ValueError('Bad resource concept/action')
    summary,example,hint=LESSONS[concept]
    texts={
      'CONCEPT_SUMMARY':f'Core idea: {summary} Check understanding by identifying the relevant construct in an original scenario.',
      'DROP_2':f'Two-option remediation: {summary} Present two competing interpretations, then ask the learner to explain why one matches the theory.',
      'WORKED_EXAMPLE':f'Worked example: {example} State the assumptions, identify the reference or incremental values, and check the conclusion.',
      'SOCRATIC_HINT':f'Guided prompt: {hint} Ask for the assumptions first; do not reveal the answer until the learner attempts an explanation.',
    }
    out=dict(row)
    out['learning_objective']=f'Provide {action.lower().replace("_"," ")} support for reasoning about {concept}.'
    out['resource_text']=texts[action]
    out['source_citation']=SOURCES[concept]
    out['review_decision']='pending';out['reviewer_record']='';out['review_date']=''
    return out

def author(items,resources):
    if len(items)!=95 or Counter(r['form'] for r in items)!=Counter(FORMS):
        raise ValueError('Source item counts do not match the original 95-slot blueprint')
    if len(resources)!=32 or {(r['concept'],r['action']) for r in resources}!={(c,a) for c in CONCEPTS for a in ACTIONS}:
        raise ValueError('Source resource grid is not 8x4')
    if len({r['item_id'] for r in items})!=95 or len({r['resource_id'] for r in resources})!=32:
        raise ValueError('Duplicate source identifiers')
    occurrence=defaultdict(int)
    drafted=[]
    for row in items:
        k=(row['concept'],row['bloom']); i=occurrence[k]; occurrence[k]+=1
        if row.get('review_decision','').strip().lower() != 'pending' or any(
            (row.get(k) or '').strip() for k in
            ('learning_objective','prompt','option_A','option_B','option_C','option_D',
             'correct_option_id','rationale','source_citation','reviewer_record',
             'review_date','difficulty_estimate')
        ):
            raise ValueError(f'Source {row["item_id"]} is already authored or reviewed; refuse to overwrite')
        drafted.append(author_item(row,i))
    for row in resources:
        if row.get('review_decision','').strip().lower() != 'pending' or any(
            (row.get(k) or '').strip() for k in
            ('learning_objective','resource_text','source_citation','reviewer_record','review_date')
        ):
            raise ValueError(f'Source {row["resource_id"]} already authored or reviewed; refuse to overwrite')
    return drafted,[author_resource(row) for row in resources]

def run(items_path,resources_path,output):
    items=load_rows(items_path,ITEM_FIELDS)
    resources=load_rows(resources_path,RESOURCE_FIELDS)
    authored_i,authored_r=author(items,resources)
    if output.exists(): raise FileExistsError(f'Output directory exists: {output}; preserve prior drafts for audit')
    output.mkdir(parents=True)
    write_rows(output/'authored_items_PENDING_REVIEW.csv',ITEM_FIELDS,authored_i)
    write_rows(output/'authored_resources_PENDING_REVIEW.csv',RESOURCE_FIELDS,authored_r)
    with (output/'review_ledger_PENDING.csv').open('w',newline='',encoding='utf8') as stream:
        w=csv.writer(stream,lineterminator='\n')
        w.writerow(['content_id','content_kind','reviewer_name','reviewer_institution','decision','review_date','review_record_uri','correction_notes'])
        for r in authored_i:w.writerow([r['item_id'],'item','','','pending','','',''])
        for r in authored_r:w.writerow([r['resource_id'],'resource','','','pending','','',''])
    # Preserve source file identities and proof that the generated drafts are new.
    manifest={'original_items_sha256':sha256(Path(items_path).read_bytes()).hexdigest(),
              'original_resources_sha256':sha256(Path(resources_path).read_bytes()).hexdigest(),
              'authored_items_sha256':sha256((output/'authored_items_PENDING_REVIEW.csv').read_bytes()).hexdigest(),
              'authored_resources_sha256':sha256((output/'authored_resources_PENDING_REVIEW.csv').read_bytes()).hexdigest(),
              'item_count':95,'resource_count':32,'reviewed_count':0,'authorized_for_human_study':False,
              'empirical_difficulty_estimated':False,'free_response_create_competency_validated':False,
              'limitations':['Draft questions; answer keys and source alignment require expert audit.',
                             'Review decisions remain pending with empty reviewer records.',
                             'Bloom create represented as recognition of good designs, not actual content creation.',
                             'Parallel pre/post forms and psychometrics unvalidated.',
                             'Generated prompts sharing a concept/Bloom may need stronger independence or alternate forms.',
                             'Each resource may need timing, reading-level and delivery validation.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items',type=Path,default=Path('docs/step96_106_authorship_slots.csv'))
    parser.add_argument('--resources',type=Path,default=Path('docs/step104_recovery_resource_slots.csv'))
    parser.add_argument('--output',type=Path,default=Path('docs/nov2_content_review_drafts'))
    args=parser.parse_args()
    print(json.dumps(run(args.items,args.resources,args.output),indent=2))

if __name__=='__main__': main()
