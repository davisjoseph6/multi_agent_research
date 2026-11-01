# Candidate instrument assessment: Lee Fatigue Scale (LFS / VAS-F)

**Status: FIRST CANDIDATE UNDER REVIEW — NOT APPROVED, NOT IMPLEMENTED, NOT LICENSED.**
Research decision recorded 2026-11-01. This file records literature-backed
requirements and open decisions; it includes **no copyrighted questionnaire
wording, response anchor text, scoring key artwork or full instrument**.
It is not institutional, ethical, privacy or publisher approval.

## Why this is being considered

The research project needs to distinguish fatigue from task workload when
investigating adaptive learning and recovery. The original VAS-F/LFS by
Lee, Hicks and Nino-Murcia (1991), doi:10.1016/0165-1781(91)90027-M,
measures *current* self-reported fatigue and energy. It is a candidate for
repeated in-session measurement, not proof of cognitive fatigue or learning
benefit. Its original validation population (75 healthy people and 57
sleep-disorder patients) differs from a student adaptive-learning sample.
Reviewer assessment of construct validity and burden is required.

## Tentative full-form implementation specification (not frozen)

| Topic | Candidate choice / still-required decision |
| --- | --- |
| Version | Original 18-item VAS-F/LFS, pending authorized source copy |
| Subscales | Fatigue: 13 items, Energy: 5 items; separate scores |
| Original recall | Current feelings ("right now"); do not reword without review/permission |
| Original response format | 100-mm analogue continuum with bipolar anchors, 0–100 per item |
| Candidate scoring | Arithmetic mean of the 13 fatigue scores and separate mean of five energy scores; confirm exact version's handling of orientation, missingness and any published norms with a qualified reviewer |
| Outcome role | Prefer *secondary* fatigue measure alongside independently measured learning outcomes; pre-register estimand, contrasts and multiplicity control |
| Timing | Investigate pre/post each learning session if change within session is the target; compare to post-session-only design and participant burden before freeze |
| Electronic migration | Screen VAS, pointer/touch/keyboard controls and accessible equivalent, exact normalized 0–100 recorded; test across devices and document measurement comparability |
| Language | Study's validated source language; do not translate ad hoc |
| Pilot | Human pilot may test usability and feasibility only after correct authorization and licensed/approved instrument; do not infer efficacy from a feasibility pilot |
| Staging | Fictional software-only demos may use distinct placeholder items, clearly labeled; never call these the Lee scale |
| Content storage | No item texts in this public repository until rights are confirmed; prefer institution-approved controlled handling |

Alternative published versions use 13 fatigue items on a numeric 0–10
scale. This is **not assumed interchangeable** with the original 18-item
paper 0–100 VAS-F. Choosing such a variant is a separate measurement decision.

## Permission and rights gate

The published reprint in *STOP, THAT and One Hundred Other Sleep Scales*
(Springer, 2012), chapter 100, explicitly states **copyright © K. A. Lee
1992; written consent required for reproduction/duplication**. A publicly
accessible form is not evidence that the form is reusable. Confirm the actual
rights holder and obtain written terms covering:
- Noncommercial academic research, number of participants, sites and dates.
- Full 18-item version or specific validated variant and any reproduction fee.
- Web-browser electronic administration (desktop, mobile and tablet),
  conversion from paper line to responsive digital VAS, and scoring.
- English language wording, accessibility adaptations and any translation.
- Whether publishing the item text in a public repository is permitted
  (default: **NO** until explicitly authorized).
- Whether the published article/instrument can be reproduced in appendices.

Do not claim written permission until the signed/emailed evidence is
received and checked.

## Code changes REQUIRED before any real study

Current `rct_candidate_content.py` rejects fatigue instruments with
anything other than **six questions** and the current
`rct_candidate.py` requires **exactly six integer responses**;
`static/rct_candidate.js` renders six (or generically many) dropdown
selects. Therefore *changing a JSON filename alone is not an LFS
implementation*.

A distinct versioned implementation must:
1. Make item count and response format explicit in the frozen bundle and
   validate source/rights evidence and item version.
2. Implement a faithful accessible eVAS, not six existing Likert selects.
3. Store all 18 raw item scores and questionnaire metadata with device/mode,
   timestamp, stage/session and provenance; compute separate fatigue/energy
   scores with version-specific rules in a tested export.
4. Specify whether pre-session administration is added; if so change stage
   transitions and analysis plan rather than silently substituting forms.
5. Add unit, browser and independent accessibility/measurement QA, including
   extrema, midpoints, keyboard/touch, mobile widths, replay/restore,
   missing data and score correctness. No use of copyrighted text in public tests.
6. Update candidate/source/content hashes, independent reviewer decisions,
   approved participant documentation and genuine release evidence.
7. Preserve the live-enrollment NO-GO gate until institutional and ethics/
   privacy/security/measurement reviews are completed.

## Assessment cautions

- Current fatigue vs sleepiness and energy vs fatigue should not be collapsed
  without a theory and evidence. The original instrument is not a direct
  measure of knowledge loss or cognitive fatigue due solely to quiz design.
- A 2023 NICE evidence review did not recommend LFS for its **particular
  clinical context** given the evidence it had; this is a caution, not a
  universal invalidation of the scale.
- Five-minute-to-ten-minute administration has been described in a reference
  compilation; other papers report shorter completion times. Pilot burden
  must be measured, not guessed.
- The protocol requires freeze of primary and secondary outcomes and
  administration timing before collecting evaluative data.

## Primary sources and methodological references

1. Lee KA, Hicks G, Nino-Murcia G. *Validity and reliability of a scale to
   assess fatigue.* Psychiatry Research 36 (1991):291–298.
   https://pubmed.ncbi.nlm.nih.gov/2062970/
2. Shahid A et al. *STOP, THAT and One Hundred Other Sleep Scales*, Springer
   2012, chapter 100 (VAS-F), reprint/rights note:
   https://www.med.upenn.edu/cbti/assets/user-content/documents/Sleep_Instruments_book_3_.pdf
3. Lerdal A et al. *Lee Fatigue And Energy Scales* 18-item subscale details:
   https://escholarship.org/uc/item/9t15m75v
4. Coons SJ et al. ISPOR ePRO mode migration recommendations:
   https://www.ispor.org/publications/journals/value-in-health/abstract/Volume-12--Issue-4/Recommendations-on-Evidence-Needed-to-Support-Measurement-Equivalence-between-Electronic-and-Paper-Based-Patient-Reported-Outcome-%28PRO%29-Measures--ISPOR-ePRO-Good-Research-Practices-Task-Force-Report
5. NICE fatigue assessment evidence review, contextual caution:
   https://www.ncbi.nlm.nih.gov/books/NBK600101/
6. eVAS vs pVAS comparability literature review:
   https://pmc.ncbi.nlm.nih.gov/articles/PMC8964617/

**Next decision:** Does the academic supervisor endorse LFS/VAS-F as a suitable
measure of in-session *subjective fatigue* for this specific learning protocol?
After that, secure legal permission and determine the exact original-version
format before any code contains the copyrighted questionnaire.
