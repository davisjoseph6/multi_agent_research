# Steps 96–106 — Draft semantic quality and leakage gate (Oct 30, 2026)

**STATUS: NOT RELEASE-READY.** This is a read-only, rule-based risk finder; it does not confirm correct answers, educational validity, authentic independent review, or human-study authorization.

## Why another check after 381 structural failures?

The 381 remaining field-level issues numerically equal 3 missing independent review fields × (95 item drafts + 32 resource drafts). That is strong evidence the *structural* omissions have been reduced. This does **not** establish validity of the questions or comparability of the pre/post instruments.

The existing generator uses only two separately phrased stems for each concept/Bloom combination but reuses each one's correct answer, distractors, rationale, and source. In the **representative fixture shipped with the generator's tests**, the pretest targets `understand`+`apply`, whereas the posttest targets `analyze`+`evaluate`. The two forms therefore target different cognitive levels, and improvement between them cannot automatically be interpreted as a change on a directly comparable scale. That is an especially serious issue for a trial whose primary outcome is a pre/post difference.

The same representative fixture has 32 assessment/practice pairs with **identical unordered answer-choice sets**, despite differing prompts. This is a leakage concern: a participant could encounter the same response options in instruction and assessment. Those findings are about the shipped fixture, NOT yet a claim about the user's actual original blueprint; run the checker on the generated CSVs.

The `create` items are multiple-choice recognition of proposed designs. They cannot be claimed to assess actual open-ended design creation.

## New read-only diagnostic

`python3 -m scripts.step96_106_semantic_quality_gate --output /tmp/ijcai_content_semantic_quality.json`

- Flags assessment/practice and pretest/posttest reuse of unordered option sets, verbatim rationales, suspiciously similar stems, and duplicate prompts.
- Reports Bloom distributions and within-concept pre/post construct mismatch.
- Flags MCQ `create` items as Bloom construct risk.
- Checks answer-key distribution and some mechanical content inconsistencies.
- Verifies that review records remain pending, but can never verify the legitimacy of an approval.
- Records SHA-256 of the actual generated draft CSVs and does not modify source or draft data.

The checker is a **triage report**. Each flag requires a human judgment; a lack of flags does not establish validity.

## Scientific remediation order

1. Confirm a content blueprint specifying **the same intended constructs and cognitive levels** in pretest and posttest, and an explicit test form equating plan. Do not silently alter the pre/post outcome definition after observing results.
2. Independently author alternate contexts, options and rationales for assessment and practice. Distinct stems alone do not prevent answer leakage. Prefer questions requiring transfer rather than recall of rehearsed distractors.
3. Have a domain specialist validate every key, theoretical interpretation, source alignment and difficulty assumption. A DOI appearing in a row is not proof it supports that particular answer.
4. Have an educational measurement specialist review construct mapping, parallel forms, reliability and psychometric plan. The Bloom `create` construct should be redesigned as an appropriately scored production task if truly required.
5. Re-run mechanical, semantic and human review gates before freezing hashes and starting any approved participant study. Keep old versions immutable for provenance.
6. Keep `review_decision=pending`, `reviewer_record=''`, `review_date=''` until an actual independent reviewer supplies verifiable review evidence. Never falsify these fields.

## What does not count as closure

- Reducing the 1,142 structural issues to 381 review issues does not establish 100% of Steps 96–106.
- Passing 1,047 regression tests does not prove assessment reliability or learning efficacy.
- The semantic audit does not substitute for independent review, real psychometric data, ethics/privacy approval or a supervisor's experimental protocol decision.

No held-out simulations or human data are used by this tool.
