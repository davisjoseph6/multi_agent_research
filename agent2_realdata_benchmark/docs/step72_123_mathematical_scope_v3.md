# Mathematical scope of the eight-concept synthetic POMCP extension

**NOT a proof of the original IJCAI manuscript's recovery guarantees.**

## Explicit synthetic state and transition

There are eight latent Boolean mastery variables, \(S\in\{0,1\}^{8}\).
Each root particle is sampled independently from the eight BKT probabilities.
The independence assumption is an approximation, not a tested fact about
human learning. Actions target one concept per decision and include QUESTION,
CONCEPT_SUMMARY, DROP_2, WORKED_EXAMPLE, and SOCRATIC_HINT. Resource actions
consume a bounded per-session budget; questions do not. For question and
DROP_2 actions, the synthetic binary observation uses slip/guess and is drawn
**before** a learning transition. Other resources have an uninformative
observation. The synthetic learning rates and action costs are configuration
hypotheses, not empirical measurements. The planner uses a horizon-3 default,
root Monte Carlo belief sampling and action/observation history-tree UCT.

## Small result that can actually be established

Let \(D_{\mathrm{true}}(S)=1-\frac18\sum_{i=1}^8 S_i\). Suppose action \(a\)
targets concept \(j\), and an unmastered concept becomes mastered with
probability \(p_a\), while an already mastered concept remains mastered.
Then, under this **specific synthetic transition law**,

\[
\mathbb E[D_{\mathrm{true}}(S')-D_{\mathrm{true}}(S)\mid S,a]
 = -\frac{p_a}{8}(1-S_j).
\]

Proof: only \(S_j\) can change. If \(S_j=1\) then it remains one and the
change is zero. Otherwise it becomes one with probability \(p_a\), which
reduces \(D_{\mathrm{true}}\) by exactly \(1/8\); otherwise the degradation
measure does not change. Taking the expectation gives the identity.

Consequences: expected synthetic **latent** degradation is nonincreasing
when \(p_a\ge 0\), but there is no general, uniform strictly negative drift:
\(p_a=0\) or \(S_j=1\) makes the conditional drift zero. Bounded two-resource
budgets and model misspecification also block any unqualified guarantee of
recovery. None of these results automatically extends to BKT *belief*
degradation, or to real learning.

## Known limitations and falsification targets

1. Initial low estimated mastery is not observed degradation.
2. The generative learning effects for the four resources are uncalibrated.
3. Finite-budget UCT outputs depend on modeling assumptions and simulation
   budget, not merely on abstract POMCP convergence claims.
4. The simulator does not model knowledge forgetting, fatigue, correlated
   concepts, dropout, or nuisance variables.
5. Fixed arm C uses a deterministic balanced round-robin concept schedule.
   This differs from the earlier v2 ID-sorted reference; compare under a
   versioned protocol rather than silently combining datasets.
6. Group A in this extension is **POMCP-assisted**, but it does NOT implement
   the historical four-stage recovery episode or prove a negative-drift bound.
   The four-stage rule-based controller remains independently available.
7. POMCP may select a small number of resources for low-mastery states; this
   is not evidence that a learner actually needed or benefited from them.
8. BKT baseline observations must use posterior-only updates, without adding
   the hypothetical learning transition during a pre-test.

## Prior to formal theoretical claims

- State the precise POMDP and controller implemented in the paper.
- Independently prove each theorem or withdraw/qualify it.
- Benchmark under multiple correctly specified and misspecified generative
  environments, with confidence intervals across replication seeds.
- Verify proposed properties on independent instances; do not tune the
  simulator solely to produce desirable outcomes for Group A.
