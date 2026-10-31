# IJCAI 2027 — Solo Research Execution Charter
**31 October 2026 | Owner: active researcher | Status: tactical plan, not a novelty or ethical approval certificate**

## Ground truth
This plan responds to the research team being temporarily unavailable due to illness. Do not depend on their return or assign them work while they are sick. The researcher can do mathematical analysis, literature review, write code, run synthetic comparisons, and prepare drafts independently. No person or AI assistant may impersonate independent expert review, institutional authorization, ethical approval, external scientific validation, or the contribution of an unavailable colleague.

**Official IJCAI 2027 dates (23:59 AoE):** January 4, 2027 abstract; January 11, 2027 full manuscript. Main track demands significant previously unpublished original AI work; 7 body pages plus 2 reference pages; double-blind manuscript and code; formal proofs and reproducible computational evidence. See https://2027.ijcai.org/ijcai-2027-call-for-papers-main-track/ and https://2027.ijcai.org/reproducibility/. The January 4 date is a **hard submission deadline**, November 2 is a **self-set research checkpoint**.

## Preserve evidence — do not try to win by tuning
Frozen branch/source provenance: through Step 110 the user confirmed local pull of commit `9809ad7a79833d4e32b7713c83c999cf426aecdc`. Latest user-reported full code suite: 1,263 passed at Step 103; Steps 104–110 are documentation-only. V6 was unfavorable; Step 100 and 102 did not establish robust Step99 superiority. Steps 103–110 are elementary mathematical examples or classical Blackwell/Le Cam arguments, not an original theorem. Human enrollment remains blocked pending actual approvals. The sealed and viewed development seeds must not be confused.

**No further StepXYZ files just to accumulate milestones or tests.** Every subsequent change must support a specific candidate paper claim or an independent falsification of that claim.

## Working-paper decision: ONE problem, ONE substantive contribution
Primary candidate (still unproven and may not be novel): cost-sensitive *historical forgetting event* inference when assessments yield noisy observations, can change latent mastery, and consume a finite, nonrenewable item inventory under structured model uncertainty.

Distinguish the history path event `F_t = 1{∃s<t: M_s=1,M_(s+1)=0}` from a low current BKT posterior and from an observed wrong answer. Explicitly say whether a later recovery cancels a "currently forgotten" event definition. Track `(M_t,F_t,inventory,θ)` for mathematical reference, but do not claim augmenting a POMDP is novel.

An **original** result might take the form of a nontrivial, provably correct bound or efficient algorithm exploiting structural assumptions of nonreusable tests that change learning, with verified improvement over established optimal stopping, adapted Blackwell information ordering, robust belief-state dynamic programming, and active change detection. These are **research requirements, not known discoveries**.

## Solo calendar and hard stop conditions

| Date | Deliverable (can be done alone) | Kill condition |
|---|---|---|
| **Oct 31 – Nov 2** | 1-page precise claim sheet: target estimand, state/action/observation timing, assumptions, loss, 3 closest results, a formal candidate proposition, and a counterexample designed to break it | If only a generic POMDP Bellman recursion, a standard TV bound, or Blackwell/Le Cam deficiency, reject it as the main-track novelty claim |
| **Nov 3 – 9** | Read and compare FULL proofs of strongest direct prior work; derive exact 1-skill 2–4-item benchmark; write proof outline and counterexamples on paper | No articulate original structural property or original problem by Nov 9: formally explore an alternative AI question, not another simulator |
| **Nov 10 – 22** | Either a defensible theorem and proof, OR a clearly specified new algorithm with complexity/validity argument and strong baselines. Fix all model assumptions before the large sweep | No plausible independently checkable result by Nov 22: do not claim IJCAI-ready main-track paper; rescope to a suitable future venue |
| **Nov 23 – Dec 6** | Implement *only* claim-critical method and exact DP oracle; ensure question/time/resource parity and independent outcome metrics; document all tried settings | Failure to reproduce baseline, leakage across development/evaluation, or unfair resources = stop performance claims |
| **Dec 7 – 20** | Frozen independent evaluation plus robustness and ablations; report **all** negative results and uncertainty; finish proof appendices | Null/negative improvement without a distinct theoretical contribution = no superiority claim |
| **Dec 21 – Jan 3** | Full 7-body-page/2-reference-page anonymous PDF, complete citations, proof checks, code-path de-identification and coauthor-review rules | Missing rigorous core claim or unsupported ethics/effectiveness claims = no main-track submission on those claims |
| **Jan 4** | Submit accurate abstract if one original paper exists and submission requirements are met | Do not register a misleading novelty claim |
| **Jan 5 – 11** | Final manuscript, anonymized supplements, reproducibility statement, final formal checks; submit by Jan 11 AoE | Do not submit incomplete/known incorrect results |

## Researcher's own 60–90-minute immediate task
On paper, write:
1. **Exact target**: what is "historical forgetting" and what period is observed? How is truth defined after recovery?
2. **Decision problem**: output `forgetting`, `no forgetting`, or `abstain`; define false-positive, false-negative and abstention costs.
3. **Reference oracle**: exact finite-inventory belief-state optimal stopping for a fixed known model and for model uncertainty. It is *not* novel, and a candidate approximation should not claim to beat the oracle on the same problem.
4. **Novelty test**: What property cannot be derived from ordinary state augmentation / Bellman recursion, adapted Blackwell garbling, Le Cam deficiency or known robust active sensing? If no rigorous answer, pivot.
5. **Falsifier**: a tiny counterexample plus a strong off-the-shelf comparator that could reveal there is no new claim.

Use technical literature, proofs and explicit counterexamples rather than asking whether a result "sounds original."

## Authorship and governance
The user can remain the active researcher and prepare all materials independently. Authorship of earlier collaborators depends on their genuine intellectual contributions and applicable publication policies; illness is not grounds to erase someone who has already earned authorship. Do not list an AI system as author. If a paper has only one legitimate human author, a solo submission is not itself prohibited by the IJCAI main-track call. Check the **reciprocal reviewer** requirement and available exemptions, author/resubmission disclosures and current submission portal before registration. The researcher is responsible for accurate proofs, complete attribution, LLM-use handling, anonymity and final paper integrity.

**Do not enroll human participants, access nonauthorized private learner data, or claim a human intervention effect** merely because project completion is now solo.

## Tools and collaboration
The assistant can serve as a *fallible analytical instrument*: check derivations, identify counterexamples, review paper paragraphs, inspect repository code, add targeted reproducibility tests and look up original-source literature. It cannot provide independent human reviewer approval or certify journal-level novelty, cannot do unrequested background work, and cannot submit the paper without proper authorization.

## Current GO / NO-GO
- **GO:** an independent, narrowly defined scientific investigation and a transparent draft.
- **NO-GO:** the existing V6/Step99 "robust self-healing superiority" story, an unwarranted universally negative drift theorem, a claim that tests prove original science, and unapproved human enrollment.
- **Conditional GO:** IJCAI 2027 main track, only when a genuinely original result, rigorous evidence and all conference requirements are satisfied.

**Most important change:** Do not wait for the team to recover, but also do not manufacture evidence that depends on people being available.
