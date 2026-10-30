# Eight Bloom `create` practice tasks — **DRAFT / NOT VALIDATED**

## What this closes and does NOT close

The existing V2 bank includes eight practice MCQs labelled `create` (one for each Behavioral Economics concept), which the semantic audit correctly flags as a construct mismatch. The new 8-task CSV requires students to **produce** a decision-analysis or research design artifact, not recognize one of four alternatives. It supplies candidate prompts and concept-specific rubric anchors. This is substantive content-authoring progress, *not* evidence that the existing eight MCQ items or the runtime have been corrected.

The original V2 95-item bank and 32 resources are byte-for-byte unchanged. All review metadata remain pending. The original 8 `create_is_multiple_choice` flags and 381 review-related failures should continue appearing until the relevant instruments and independent evidence actually change.

## Proposed analytic rubric (independent review required)

Four criteria each rated 0, 1 or 2 (total 0–8):

1. **Domain accuracy:** Correctly applies the named Behavioral Economics theory; concept-specific anchor supplied in the CSV.
2. **Original design quality:** Produces a new and internally coherent calculation, experiment, interface, or decision memo; concept-specific anchor supplied.
3. **Reasoning and justification:** States assumptions, supports decisions with coherent evidence and identifies alternatives or confounds.
4. **Clarity and constraints:** Delivers all requested components, uses transparent formatting and does not silently change outcomes across conditions.

Anchor definitions: `0` absent/incorrect; `1` partially correct with material omissions; `2` meets criterion without material error. These are **proposed** anchors only: sample answers, adjudication rules and rater calibration are needed before any score can be interpreted. Expert reviewers should verify each content-specific accuracy/design anchor and source citation.

## Real implementation work before replacing the eight MCQs

- Add a genuine constructed-response question type to the server-side item schema, API, browser, persistence and replay. Do not repurpose `correct_option_id` to encode essay answers.
- Define a blinded, at least two-rater scoring procedure with disagreement resolution, rater-training examples, documented versioned scoring rubrics and a prespecified reliability statistic; secure handling of personal responses.
- Check intervention time comparability. The 8 open-response tasks may take substantially longer than MCQs, impacting the 55-action session and fatigue measures; re-evaluate the fairness/dosage protocol.
- Retain the same eight concept identities; decide with the research team whether Bloom `create` is an instructional practice target, an exploratory outcome, or should be excluded from the primary pre/post estimand.
- Request independent subject-matter, assessment-design, accessibility and ethics/privacy reviews. Obtain institutional approvals before any real participants.
- Verify legal access to source texts. Existing citation strings are carried over unchanged from the current V2 bank; they are not independent source verification.

**Do not** edit the semantic checker to suppress the warnings or claim 100% because these prompts are written. This package also does not establish a novel or efficacious IJCAI recovery algorithm.
