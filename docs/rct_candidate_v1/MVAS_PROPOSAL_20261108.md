# Candidate fatigue measure review — Mental Fatigue Visual Analogue Scale (M-VAS)

**Status: proposal, NOT approved or integrated.** Prepared 2026-11-08. PI, psychometrics reviewer, DPO and ethics pathway must sign off. Do not replace the `fatigue_REHEARSAL_ONLY.json` fixture and call it validated.

## Research fit

Target construct is **immediate perceived mental fatigue during cognitively demanding educational work**, not clinical disease fatigue or days/weeks of tiredness. For brief repeated administration, a single current-state visual analogue question is plausible and less burdensome than multi-item health or trait instruments.

**Direct experimental precedent:** `Mental Fatigue Negatively Impacts Cognitive and Physical Performance Outcomes: A Large-Scale Randomized Crossover Trial` (https://pmc.ncbi.nlm.nih.gov/articles/PMC12746782/). The trial used **a 10-cm line** with a mental-fatigue question and endpoints equivalent to "not at all" / "completely exhausted"; reported increased M-VAS after a 45-minute cognitive Stroop challenge compared with control. This supports responsiveness under that experimental context, NOT automatically a validated digital 0..100 slider for education and not a universal clinically validated instrument.

Related practicality evidence: `Comparing the Effects of Three Cognitive Tasks on Indicators of Mental Fatigue`, PMID: 31188721 (https://pubmed.ncbi.nlm.nih.gov/31188721/), reports usefulness of simple VAS around cognitive tasks.

## Recommended candidate specification (must be frozen by PI)

- Instrument ID: `MVAS_MENTAL_FATIGUE_STATE_0_100_PROPOSED_V1`.
- Prompt for review (adaptation, not verified verbatim licensed item): **"How mentally fatigued do you feel right now?"** 
- Left anchor (0): **"Not at all"**. Right anchor (100): **"Completely exhausted"**. Confirm wording/translation against permitted instrument use and language validation.
- Administer at **immediate pre-learning** and **immediate post-learning** on each of **3** visits, total six observations per student. No delayed recall interval.
- Each entry must explicitly require a user-chosen response, no preselected middle value; store **integer 0..100** as `rating`, `session`, `timepoint` (`pre` or `post`), authenticated timestamp, version, input mode and missing-response reason.
- Provide accessible keyboard-number alternative to draggable slider, visible endpoints, high-contrast labels, screen-reader semantics, zoom and mobile; do not silently treat missing as zero.
- Proposed score `delta = post - pre` on the same visit; report original values and within-person trajectories. Greater delta = greater reported short-term fatigue. No diagnostic threshold or fatigue reduction claim.

## Validity and use caveats

The referenced experiment used a physical **100-mm / 10-cm VAS**; mapping to a **digital 101-position numeric input** may alter response behavior and resolution. A 0..100 number is not by itself a validated psychometric *scale*; evidence for responsiveness and reliability in this setting must be reviewed. Get the original exact instrument anchors, permission/license status, French/English translations and digital-equivalence decision in writing. Avoid copying extended published question banks.

Potential measurement concerns: anchoring with repeated measures, demand characteristics across visible arms, baseline fatigue from visit-1 pretest, screen/device layout, differential time-on-task due Arm A extra resources, expectation bias, and fatigue from posttest if placement is inconsistent.

If exact M-VAS adaptation cannot be justified, the team should evaluate alternatives with measurement expertise. The four-item mental-fatigue subscale sometimes attributed to MFI-20 is NOT interchangeable with a single momentary VAS; its wording, recall period and rights must be reviewed separately.

## Critical software change required

The current `ContentBundle` in `src/prototype/rct_candidate_content.py` validates **exactly six questionnaire prompts**, and `RCTCandidateEngine` issues **one FATIGUE action after each session**, expecting **six responses** at once. This is a schema and state-machine mismatch with **one M-VAS response pre and post each session**.

Therefore, an approved pilot candidate needs: a **new instrument object, candidate version, state transitions, API request schema, UI, timestamping, quality checks, analytics and migrations on a FRESH pilot database**. Rehearsal fixture and currently deployed fictional database must remain unchanged and not be presented as approved M-VAS.

## Proposed reviewer acceptance checklist

- [ ] Official source and exact question/anchor wording independently confirmed.
- [ ] Right to use/reproduce/translate/distribute confirmed in writing.
- [ ] Original 10-cm vs digital 0..100 adaptation method and comparability accepted.
- [ ] Language versions and accessibility testing accepted.
- [ ] Six timepoints and assessment order approved; no extra assessment burden conflicts.
- [ ] Storage/retention/privacy classification and DPO controls approved.
- [ ] Pre/post scoring and missingness handling frozen in SAP.
- [ ] New code and synthetic three-session automated tests reviewed and passed.
- [ ] Human enrollment institutional gate reviewed and signed.

**Decision:** M-VAS is currently the preferred candidate secondary measurement, **not yet approved for participants**.
