# Decisions to freeze before human enrollment

This candidate preserves the default A/B/C policy contrast. It does not replace
supervisor decisions, create a registration, or amend an approved protocol.

| Decision | Candidate behavior | Required decision/evidence |
|---|---|---|
| Main contrast | A: V3 POMCP; B: greedy without recovery; C: balanced fixed sequence | Sponsor selects package effect or recovery-specific effect |
| Optional matched control | `control: pomcp_no_recovery` makes B the same V3 selection routine with recovery unavailable | Explicit protocol amendment and new frozen database, before enrollment |
| Algorithm | Existing eight-concept V3 selector, 240 simulations, horizon 3, historical assumed effects/costs | Confirm exact parameter/model/source fingerprint |
| Recovery budget | Two individual resources per session, maximum six total | Confirm; this is not two four-stage episodes |
| Instructional dose | 55 practice questions, plus A's recovery; time is recorded, not equalized | Approve total-package estimand or specify a matched-time design |
| Sequencing | 16 pretest; 20/20/15 practice, each followed by six questionnaire responses; 16 posttest | Confirm timing and whether sessions are consecutive; no between-day scheduling is enforced |
| Practice bank | Exactly 55 items, all eventually used in each completed journey | Effects concern ordering and additional recovery; there is no 55-of-larger-bank coverage comparison |
| Outcomes | Independently scored 16-item pre/post, no assessment feedback; incomplete scores exported as null | Specify primary contrast, estimand, analysis, missingness and multiplicity before enrollment |
| Fatigue | Six clearly labeled rehearsal fixtures | Replace with the actual approved instrument and scoring; no fatigue efficacy claim from fixtures |
| Bloom create | Existing MCQ items retained for recognition practice | Do not claim measured creation; approve this narrower scope or implement and validate constructed responses |
| Resource delivery | Text; two-option DROP_2 response; text resources allow completion/skip | Review readability, timing and whether this intervention delivers the intended teaching |
| Belief updates | Historical BKT pretest posterior, practice update; no artificial increase after a text acknowledgment | Review model mismatch and interpretation; latent mastery remains inferred |
| DROP_2 observation | Historical V3 uses its fixed guess assumption, despite a two-option item | Retained for parity, not justified calibration; decide before freezing |
| Randomization | Server-side equal-probability permuted blocks of 6 or 9; assigned after agreement; concealed from browser | Confirm individual unit, any required strata, allocation management and recruitment |
| Identity | One unpredictable invitation per pseudonymous record | Institution must issue one invitation per eligible person and keep identity mapping separately |
| Withdrawal | Stops future participation; does not automatically erase previous records | Approve data-rights and retention process and put it in information notice |
| Hosting | Loopback rehearsal; gated WSGI live factory | Institution approves host, TLS, access, proxy, backup, retention, load and device QA |

Recommended primary analysis draft for statistical review: intention-to-treat
comparison of posttest scores for A versus B, accounting for pretest and any
randomization strata, with confidence intervals. State the method for incomplete
outcomes and all secondary comparisons, including C. Do not analyze only
completers without addressing attrition. The 9-person software smoke run is not
a sample-size calculation. Derive sample size from a justified meaningful effect,
variability, power, allocation, multiplicity, clustering if applicable, and attrition.

Pre-register the final protocol and analysis before the first randomized human
participant. Record deviations and amendments; do not silently replace V3 with
V6 or change assumptions after examining study outcomes.

V6's five-scenario negative/uncertain audit should be retained and disclosed in
the research rationale. It does not establish that the V3 policy is ineffective,
nor does it establish a V3 benefit. An authorized RCT can estimate an unknown
effect. Simulated success is not a required prior proof of that effect.
