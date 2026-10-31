# Step 103 — Research triage: why post-only low mastery cannot certify deterioration

**Research status:** exact toy-model mathematics, NOT an IJCAI novelty claim, NOT a deployed detection system, NOT an estimate of human forgetting and NOT a statement that Bayesian Knowledge Tracing is generally non-identifiable.

## Frozen prior computational results

Step 100 evaluated 30 paired synthetic learners per scenario with recovery resources allowed. Step 99 minus V3 16-item synthetic posttest accuracy was:

| Environment | Difference | Descriptive 95% bootstrap range |
|---|---:|---:|
| nominal | +0.006250 | [−0.033333,+0.045833] |
| half_learning | −0.018750 | [−0.056250,+0.018750] |
| noisy_observations | −0.004167 | [−0.029167,+0.016667] |
| forgetting_shift | +0.037500 | [−0.014583,+0.089583] |

Step 102 used the unchanged Step 100 *external environment* and the same 30 previously used development seeds, with identical **55 practice questions and zero recovery actions** in the two policy arms. The researcher reported 1,242 passing tests, clean Git status and four frozen-simulator parity cases passed at `af7962f76b4a5c49ab14d29ee4474fd855b0cf60`.

| Environment | Step99 practice-only − V3 practice-only | Descriptive interval |
|---|---:|---:|
| nominal | −0.004167 | [−0.043750,+0.029167] |
| half_learning | −0.037500 | [−0.075000,+0.002083] |
| noisy_observations | +0.008333 | [−0.033333,+0.050000] |
| forgetting_shift | −0.035417 | [−0.070833,0.000000] |

**Disposition:** NO-GO for asserting Step 99 superiority under either evaluation. The second experiment does not test recovery at all, so it cannot substantiate a self-healing claim. Both datasets are synthetic and exploratory. Their raw JSON outputs remain on the researcher's workstation at `/tmp/ijcai_step100_full_01.json` and `/tmp/ijcai_step102_full_01.json` and have not been imported here. Do not choose a preferred scenario or tweak existing benchmark values.

## Restricted exact observational-equivalence example

Consider one binary latent concept and answers generated with slip \\(s\\) and guess \\(g\\). Two entirely distinct histories occur **before observation begins**:

- **F (possible forgetting):** certainly mastered just before a hidden transition; forgets with probability \\(f\\), otherwise stays mastered.
- **L (initially weak):** has mastery probability \\(1-f\\) from the outset; never forgets.

Under **identical subsequent learning, forgetting and emission dynamics**, and identical action policies based on observations, both induce the same current mastery distribution. By the Markov property, their post-only observable histories therefore have the *same distribution*. The elementary finite model implemented in `src/prototype/step103_post_only_identification.py` is even narrower: the latent state never changes again, and all post responses conditionally independently follow the common slip/guess emission.

For any binary response string \\(y_{1:T}\\), both post-only models have likelihood

\\[
P_F(y_{1:T})=P_L(y_{1:T})
=(1-f)\prod_{t=1}^{T}P(y_t\mid M)
+f\prod_{t=1}^{T}P(y_t\mid U).
\\]

Thus their total-variation distance is exactly zero and optimal **equal-prior** Bayes classification error is \\(1/2\\) for *any number* of post-only observations, **under these restricted assumptions**. This does NOT mean a learner with a recorded earlier baseline is indistinguishable from a low-initial-mastery learner.

### One observed pretransition response

Suppose one pretransition answer is actually observed. Under F, that answer is emitted from a certainly mastered state; under L, it comes from the same mastery mixture \\(1-f\\). The future observations have the same emission model. Exact enumeration then gives the total-variation distance for the entire pre+post sequence

\\[
\operatorname{TV}(P_F,P_L)=f\lvert(1-s)-g\rvert.
\\]

For \\(f=1/4,s=1/10,g=1/4\\), this is \\(13/80\\), and equal-prior Bayes error is \\(67/160\\), compared with \\(1/2\\) with post-only observations. The result shows that *observed historical information* can be crucial; it does not validate a practical detector or measure real students' forgetting.

Proof: with post-string likelihoods \\(p_M(y),p_U(y)\\) and pre-answer \\(z\\), subtract the joint likelihoods. The difference is \\(f[P(z\mid M)-P(z\mid U)]p_U(y)\\). Sum its absolute value over post strings and both pre-answer possibilities, dividing by two.

## Important prior-art correction

Do **not** claim that BKT/HMMs are generally non-identifiable. Doroudi & Brunskill, *The Misidentified Identifiability Problem of Bayesian Knowledge Tracing* (EDM 2017), explain that BKT is identifiable under mild conditions, while *semantic model degeneracy* is a distinct issue. The restricted counterexample above compares two unobserved histories with a coincident present-state distribution, not two unrestricted identifiable BKT parameters learned from complete longitudinal traces.

- Doroudi & Brunskill (2017): https://www.cs.cmu.edu/~shayand/papers/EDM2017.pdf
- Knowledge Tracing survey (ACM Computing Surveys): https://doi.org/10.1145/3569576
- Gassiat, Le Corff & Lehéricy (2020), positive HMM identifiability results for their studied class: https://www.jmlr.org/papers/v21/19-802.html
- Closest POMDP teaching benchmark: Rafferty et al. (2016), https://doi.org/10.1111/cogs.12290

**This is an elementary identifiability warning, not IJCAI novelty.**

## Actionable supervisory decision by Monday November 2

A. **Investigate a substantive new learning-theory result** only if the team can articulate a nontrivial operational target (e.g. risk-controlled deterioration decisions with finite measurement costs) that prior sequential-testing, constrained POMDP and latent-state identifiability theory does *not* already resolve. Require an exact theorem and a useful bound.

B. **Pivot to a genuine new robust constrained decision method** only after a closest-prior-art screen and an evaluation design with matched resources and independently calibrated intervention effects. Step 99 currently lacks meaningful superiority evidence.

C. **Reframe the IJCAI 2027 submission** if neither path has a distinct verified contribution in time; a stable app and a simulated intervention without an algorithmic novelty claim are insufficient for main track.

Do not initiate the real-human RCT until independent assessment, protocol, ethics/institutional authorization, privacy, deployment and statistical review requirements are met.
