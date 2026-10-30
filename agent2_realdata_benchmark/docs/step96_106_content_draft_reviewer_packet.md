# Steps 96–106 — Content authoring and independent review packet

**Status:** all generated content is **DRAFT / NOT APPROVED / NOT FOR HUMAN STUDY**.

The draft bank preserves the existing 95 item IDs and metadata (16 pretest, 16 posttest, 55 practice, 8 two-option recovery probes) and all 32 resource IDs (eight concepts × four actions). It never edits canonical source slots. All original authored or previously reviewed rows trigger fail-closed rejection rather than being overwritten.

## Independent review sequence

1. **Researcher editorial review:** Check each factual statement, arithmetic example, question-key consistency, grammatical clarity, demographic assumptions, copyright, reusability, accessibility and reading level. Revise the draft copy, never retroactively alter original test results.
2. **Behavioral economics expert:** Verify all 95 prompt/answer/rationale/source associations and 32 substantive recovery resources. Source references are scholarly provenance, not evidence of prior expert item approval. Record independently authored corrections, dated reviewer identity and verifiable review record.
3. **Educational measurement specialist:** Validate the eight constructs and learning objectives, expected cognitive level, the purported Bloom `create` items, 16/16 pre/post **parallel form** comparability, answer-key biases, difficulty estimates and absence of material cross-form leakage.
4. **Pilot participants and authorized oversight:** Required for empirical item difficulty, reliability, factor/construct validity, engagement and fatigue measurement, and for any genuine participant intervention claims. Seek institutional ethics/privacy determination **before** recruitment.
5. **Content freezing:** Only after review decisions and authorized protocol are complete, attach signed reviews, actual dates, item hashes, final release versions and a distinct approved export. Do not backdate, invent approvals or mark external gates closed from scripts.

## Special warnings

- The script estimates difficulty heuristically by Bloom level only. This is a declared *author's provisional estimate*, **not measured item difficulty**.
- `create` is represented as selecting the best design among options; this does not test actual open-ended creativity and must not be claimed to meet the full Bloom `create` construct without reassessment.
- The initial bank deliberately favors transparent foundational concepts. It is **not** aligned to a confirmed education level, target population, validated syllabus, content difficulty balance, or item response theory model.
- Several item pairs share the same conceptual principle. Duplicate-prompt rejection is insufficient to demonstrate pre/post independence or prevent conceptual leakage. Expert alternate-form design is mandatory.
- The 32 interventions are brief prototype scripts, not timed or empirically validated resources. `DROP_2` remediation text is distinct from its two-option question item.
- There is no automatic path from pending reviews to approved reviews. Any eventual approval must be recorded by a real independent reviewer, outside this utility.
- Original authored slot IDs and file SHA-256 hashes are stored in the draft manifest; never overwrite the canonical source rows with generated data.

## Sources for content verification (do not infer endorsement)

- von Neumann & Morgenstern, *Theory of Games and Economic Behavior* (1944), Princeton University Press — utility and lotteries.
- Kahneman & Tversky (1979), *Prospect Theory: An Analysis of Decision under Risk*, Econometrica, DOI 10.2307/1914185 — prospect theory.
- Tversky & Kahneman (1991), *Loss Aversion in Riskless Choice*, Quarterly Journal of Economics, DOI 10.2307/2937956 — reference dependence and loss aversion.
- Tversky & Kahneman (1974), *Judgment under Uncertainty*, Science, DOI 10.1126/science.185.4157.1124 — availability, anchoring, representativeness.
- Arkes & Blumer (1985), *The Psychology of Sunk Cost*, Organizational Behavior and Human Decision Processes, DOI 10.1016/0749-5978(85)90049-4.
- Tversky & Kahneman (1981), *The Framing of Decisions and the Psychology of Choice*, Science, DOI 10.1126/science.7455683.
- Thaler & Sunstein, *Nudge: Improving Decisions About Health, Wealth, and Happiness* (2008), Yale University Press, ISBN 9780300122237.

## Expected existing structural audit behavior

Run the actual unchanged `scripts/step96_106_content_audit.py --items <draft CSV> --resources <draft CSV>`.

Even after all draft text fields are populated, **the audit must exit nonzero** because reviews are pending; it should still record expert_review_verified=false and authorized_for_human_study=false. If a structural failure beyond pending reviews appears, fix the actual draft content, not the validator. Review the issue count; do not promise a particular count without running it against the live original row distribution.
