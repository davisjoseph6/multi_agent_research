# IJCAI November 2 sprint — V2 pre/post assessment editorial revision

**Status: researcher's/AI-assisted item draft, not independent expert-reviewed, not a validated assessment, not authorized for human study.**

## Specific reason for the revision

The user's actual October 30 semantic audit of 95 draft items and 32 recovery resources reported:

- 62 shared sets of four answer choices, often across pre/post or practice/assessment;
- 16 identical pre/post rationales;
- 8 multiple-choice items assigned Bloom `create` but not testing production of original content.

Both 16-item pretest and 16-item posttest had 8 `understand` and 8 `apply` questions, with one per concept/level. Thus matching the blueprint is already feasible, but identical answer options and identical rationales pose exposure/leakage risks. The proposed V2 draft replaces **all 32 pre/post items** with distinct authored vignettes, context-specific distractors, and different explanatory rationales. It preserves the same eight concepts and same Bloom level for each item and does not use machine paraphrasing to disguise identical answer sets.

## What is retained and protected

- **All original item identifiers** and rows are retained; practice (55), recovery probes (8), and resources (32) are untouched.
- The original correct option *letter* is preserved, but its answer text and the accompanying distractors are newly authored. Keeping the letter does not validate the answer.
- Previously entered objective, source citation, heuristic difficulty estimates and all metadata are preserved. Difficulty remains unmeasured.
- All 127 content/review records must remain PENDING, with no invented reviewer information.
- The script checks source item SHA-256 `d80adfb754cd44c5e19146974cc72fcaef9da7985ab74eb2f84ffac3bd220c79` and resource SHA-256 `b5e33fa2062853557e6fff48770f850c057ddfee2dc4468ecccaacc4ca40336b`, refusing edits to unrecognized content.
- A new versioned directory is created, and the original directory is never overwritten.
- The actual semantic audit runs *before and after* and must show fewer high/blocking flags, or the script fails closed.

## Limits that must remain visible

1. These are editorially distinct questions, **not proven equivalent parallel forms**. A domain expert must inspect all 32 item/answer/rationale trios, and an educational measurement expert must assess construct alignment and comparable difficulty.
2. In particular, several `apply` items test arithmetic or classification that may not directly measure susceptibility to behavioral biases. This is a construct-validity concern requiring review, not an issue that a text-leakage checker can resolve.
3. The Bloom `create` level still has eight multiple-choice practice questions, which cannot validate open-ended creation. Repairing that gap requires separately deciding on open-response tasks, their scoring rubric, software support, and independent review; merely renaming the questions does not solve it.
4. The existing 55 practice questions and 32 recovery resources may still over-repeat concepts or answers; their semantic validity requires separate review. No claim of factual validity arises from an audit with zero repetition flags.
5. Pre/post equivalence requires both subject-matter review and evidence from appropriately authorized pilot participants or psychometric evaluation. Heuristic numerical difficulty scores are not measured item parameters.
6. The original structural content auditor will still require authentic independent reviewer identities, review dates and verifiable records, and must still return a nonzero exit code while reviews remain pending.
7. Do not release generated content to participants or mark Steps 96–106 as fully complete from this automated revision alone.

## Independent test notes

In an *isolated representative fixture* with 95 items and 32 resources following the observed matched pre/post Bloom blueprint, 12 new tests passed. The original fixture produced 48 shared choice sets and 16 shared rationales (64 high flags), while the V2 draft had none of those text-repetition flags. Eight Bloom `create` construct flags remained. These counts describe the fixture, not the user's actual files. **The real file counts must be obtained in the WSL checkout.**

## Safely run against the real October 30 generated drafts

Run from `~/multi_agent_research/agent2_realdata_benchmark`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step96_106_revise_parallel_forms
```

The script will create `docs/nov2_assessment_revisions_v2_PENDING_REVIEW/` containing a new authored items CSV, the unchanged resources CSV, and a provenance manifest. It will refuse to overwrite the directory or work on unfamiliar source hashes.

Then run BOTH original checkers on V2 (do not change either checker):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step96_106_semantic_quality_gate \
  --items docs/nov2_assessment_revisions_v2_PENDING_REVIEW/authored_items_PENDING_REVIEW.csv \
  --resources docs/nov2_assessment_revisions_v2_PENDING_REVIEW/authored_resources_PENDING_REVIEW.csv \
  --output /tmp/ijcai_v2_semantic_quality.json

PYTHONDONTWRITEBYTECODE=1 python3 scripts/step96_106_content_audit.py \
  --items docs/nov2_assessment_revisions_v2_PENDING_REVIEW/authored_items_PENDING_REVIEW.csv \
  --resources docs/nov2_assessment_revisions_v2_PENDING_REVIEW/authored_resources_PENDING_REVIEW.csv \
  > /tmp/ijcai_v2_structural_audit.json
```

The second command is expected to exit nonzero until real independent reviews have been completed. Include the exit code and the complete JSON in any claim about progress.

## Scientific next step

Have a behavioral-economics reviewer and a psychometrics specialist review these revised forms. Separately prioritize the IJCAI algorithm's originality and a properly controlled recovery ablation; this content revision does not establish research novelty or self-healing efficacy.
