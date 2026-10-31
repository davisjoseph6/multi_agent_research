# IJCAI 2027 — One-page research decision for supervisory review

**Draft, 31 October 2026 | Decision sought by Monday 2 November 2026**

## Intended conference result

An original **main-track AI research contribution** on decisions under partially observable, finite-resource tutoring environments, with mathematically valid claims, reproducible software and appropriately calibrated empirical evidence. The three-arm human intervention candidate exists but **is not approved for enrollment**.

## Reproducible current position

- Existing RCT software rehearsal: 9 fictional completed participants (A/B/C: 3 each); original candidate preflight lists substantial unresolved content, measurement, institutional, privacy, and independent-QA blockers.
- On the new nonproduction research branch, 1,221 project tests passed at commit `d62c04b5`; the Step 100 fixed 30-seed paired comparison has completed. Test passes establish code integrity only.
- Step 95 V6 deterioration-trigger mechanism: broad five-scenario development screen **NO-GO**; results include nonpositive recovery contrasts.
- Step 94/97: an exact counterexample prevents a global strict negative-drift claim for one V3 policy configuration. A conditional randomized-coverage drift certificate applies only to an assumed eight-concept model with full action support.
- Step 98: a 55-question bank has finite concept inventory; after six Nudge Theory questions are exhausted, no further V3 root action can target it. A uniform statewise mastery drift guarantee therefore need not remain valid.
- Step 99: a standalone research-only POMCP-style planner now tracks the consumable inventory and 20/20/15 sessions, including mandatory practice-question warmups. It is not the deployed trial controller.
- Step 100: independent synthetic 16-question posttest; Step 99 minus original V3 mean differences: `nominal +0.00625`, `half_learning -0.01875`, `noisy_observations -0.00417`, `forgetting_shift +0.03750`. **All four descriptive intervals cross zero. No robust superiority has been established.**

## Key research distinction, not yet proven novel

POMDP planning for teaching and risk shielding of POMCP are prior art (Rafferty et al. 2016; Mazzi et al. 2023). Simply adding an inventory counter or a deterioration threshold to POMCP will not establish IJCAI novelty.

**Question for supervisory decision:** is there a genuinely new, mathematically nontrivial algorithm or characterization for **resource-feasible belief-space recovery under uncertain learning/forgetting transitions**, with clear advantage relative to the most relevant existing constrained/robust POMDP methods? If not, choose a different central AI problem before further engineering.

## Candidate A — robust constrained belief-space decision method

Specify an uncertainty set over learner transitions and observations, an intervention-cost budget, a finite item inventory, and an explicit metric such as robust independent end-of-study mastery or a regret bound. The research contribution would need (i) an algorithm that does something not achieved by established robust/constrained POMDP or POMCP shielding, (ii) sound proof about **the executed algorithm**, and (iii) improvements over matched-dose state-of-the-art baselines under model shift. **No such novel result is established today.**

## Candidate B — rigorous limitation and impossibility result

Investigate an informative impossibility/identifiability theorem: what forms of deterioration cannot be distinguished from noisy responses under a finite probing budget, and how much additional independent evidence is necessary to make a reliable intervention decision? Distinguish latent forgetting, posterior BKT revision and lower initial mastery. This alternative may be more defensible if Candidate A's novelty/efficacy is weak, but requires a substantive theorem and tight related-work screen. **No new theorem of that strength is established today.**

## Concrete questions requiring research-supervisor decisions

1. What exact original theorem, algorithm or AI problem is the main-track paper about—and which prior work is its closest competitor?
2. Which hypothetical learning effects can be calibrated with authorized data, and which must remain scenario assumptions?
3. Is the primary evaluated contrast Step 99 versus V3, recovery versus matched-dose non-recovery, or a different new algorithm versus robust constrained POMDP?
4. Which simulator and evaluation split will be frozen independently, given that Step 95 and Step 100 development outcomes are already known?
5. Should we invest effort in a human RCT for a future research paper, given that ethical and measurement authorizations are not yet available?

**Recommendation for Monday:** keep the code freeze and negative results; complete Step 101 source/report audit; obtain a supervisory direction and an originality screen before large-scale new policy development. No ethics or human-learning claims until actual approvals and outcomes.
